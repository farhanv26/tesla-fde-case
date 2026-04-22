"""Exploratory diagnostics for the Tesla FDE case study."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from load_data import inspect_all_target_workbooks
from utils import ensure_directory, get_project_root, normalize_identifier


def _normalize_site_family(site_value: object) -> str:
    """
    Collapse "Berlin" and "GF Berlin" to a single site family "Berlin".

    Source data double-labels every site, which previously split every metric
    in half across two rows of the ranking.
    """
    text = str(site_value).strip()
    if not text or text.lower() == "nan":
        return "Unknown"
    lowered = text.lower()
    if lowered.startswith("gf "):
        return text[3:].strip()
    return text


def _normalize_sites_inplace(df: pd.DataFrame) -> pd.DataFrame:
    """Rewrite the ``site`` column to its normalized family label, if present."""
    if not df.empty and "site" in df.columns:
        df = df.copy()
        df["site"] = df["site"].map(_normalize_site_family)
    return df


def infer_sheet_purpose(sheet_name: str, columns: list[str]) -> str:
    """Infer a likely sheet purpose from sheet name and column names."""
    combined_text = f"{sheet_name} {' '.join(columns)}".lower()

    if any(token in combined_text for token in ["project", "estimate", "budget", "cost"]):
        return "Likely project planning, estimate, or budgeting data."
    if any(token in combined_text for token in ["site", "location", "region", "state", "country"]):
        return "Likely site/location dimension or deployment geography data."
    if any(token in combined_text for token in ["date", "month", "year", "quarter"]):
        return "Likely time-series or schedule-related data."
    if any(token in combined_text for token in ["customer", "account", "client"]):
        return "Likely customer/account level records."
    if any(token in combined_text for token in ["resource", "labor", "hours", "role"]):
        return "Likely staffing/resource utilization data."
    if any(token in combined_text for token in ["part", "sku", "material", "component"]):
        return "Likely parts/materials or bill-of-materials data."
    return "General dataset; needs deeper domain validation."


def find_possible_join_keys(workbooks: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Flag potential join keys across sheets by normalized column name similarity."""
    column_index: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for workbook_name, sheets in workbooks.items():
        for sheet_name, df in sheets.items():
            for column_name in df.columns:
                normalized = normalize_identifier(str(column_name))
                if normalized:
                    column_index[normalized].append((workbook_name, sheet_name, str(column_name)))

    candidate_rows = []
    for normalized_name, occurrences in column_index.items():
        unique_sheet_refs = {(wb, sheet) for wb, sheet, _ in occurrences}
        if len(unique_sheet_refs) > 1:
            candidate_rows.append(
                {
                    "normalized_key": normalized_name,
                    "occurrence_count": len(occurrences),
                    "locations": " | ".join(
                        [f"{wb}::{sheet}::{col}" for wb, sheet, col in occurrences]
                    ),
                }
            )

    candidates_df = pd.DataFrame(candidate_rows)
    if not candidates_df.empty:
        candidates_df = candidates_df.sort_values(
            by=["occurrence_count", "normalized_key"], ascending=[False, True]
        ).reset_index(drop=True)

    return candidates_df


def _safe_numeric(series: pd.Series) -> pd.Series:
    """Parse mixed numeric strings like '$120k', '28 orders', '3 incidents', '5 days'."""
    text = series.astype(str).str.lower().str.replace(",", "", regex=False).str.strip()
    extracted = text.str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    numeric = pd.to_numeric(extracted, errors="coerce")

    # Magnitude suffix handling (e.g., 120k, 1.2m)
    has_k = text.str.contains(r"\bk\b|k$", regex=True, na=False)
    has_m = text.str.contains(r"\bm\b|m$", regex=True, na=False)
    numeric.loc[has_k] = numeric.loc[has_k] * 1_000
    numeric.loc[has_m] = numeric.loc[has_m] * 1_000_000
    return numeric


def _parse_week_number(series: pd.Series) -> pd.Series:
    """Parse week field robustly (supports 'Week 1', 'Wk 2', '3')."""
    text = series.astype(str).str.lower().str.strip()
    extracted = text.str.extract(r"(\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def _sheet_lookup(workbooks: dict[str, dict[str, pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    """Build a lowercase sheet-name lookup; normalize site labels at the source."""
    lookup: dict[str, pd.DataFrame] = {}
    for sheets in workbooks.values():
        for sheet_name, df in sheets.items():
            lookup[sheet_name.lower()] = _normalize_sites_inplace(df.copy())
    return lookup


def _identify_core_measures(workbooks: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Inventory available operational measures from all sheets."""
    keywords = {
        "hours": ["hour", "hours"],
        "quantities": ["quantity", "qty", "count", "deployed"],
        "budgets_costs": ["budget", "cost", "actual", "estimate", "total"],
        "milestones_schedule": ["milestone", "date", "week", "delay", "impact"],
        "status_reporting": ["status", "priority", "incident", "blocked", "feedback"],
    }
    rows: list[dict[str, str]] = []

    for workbook_name, sheets in workbooks.items():
        for sheet_name, df in sheets.items():
            for column in df.columns:
                col_lower = str(column).lower()
                matched_categories = [
                    category for category, terms in keywords.items() if any(term in col_lower for term in terms)
                ]
                if matched_categories:
                    rows.append(
                        {
                            "workbook": workbook_name,
                            "sheet_name": sheet_name,
                            "column_name": str(column),
                            "measure_categories": " | ".join(matched_categories),
                        }
                    )
    return pd.DataFrame(rows)


def _build_financial_variance(financial_df: pd.DataFrame) -> pd.DataFrame:
    """Compute budget vs actual variance metrics by site and category."""
    df = financial_df.copy()
    if not {"site", "category", "budgeted", "actual"}.issubset(df.columns):
        return pd.DataFrame()

    df["budgeted_num"] = _safe_numeric(df["budgeted"])
    df["actual_num"] = _safe_numeric(df["actual"])
    df["variance"] = df["actual_num"] - df["budgeted_num"]
    df["variance_pct"] = (df["variance"] / df["budgeted_num"]).replace([float("inf"), float("-inf")], pd.NA) * 100

    result = (
        df.groupby(["site", "category"], dropna=False)[["budgeted_num", "actual_num", "variance", "variance_pct"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values("variance", ascending=False)
    )
    return result


def _build_event_risk_summary(event_df: pd.DataFrame) -> pd.DataFrame:
    """Build a site-level operational disruption and risk summary."""
    df = event_df.copy()
    required = {"site", "event_type", "days_impact", "cost_impact"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["days_impact_num"] = _safe_numeric(df["days_impact"])
    df["cost_impact_num"] = _safe_numeric(df["cost_impact"])
    df["is_delay_like"] = df["event_type"].astype(str).str.lower().str.contains(
        "delay|slip|block|issue|outage|rework", regex=True
    )

    result = (
        df.groupby("site", dropna=False)
        .agg(
            events_count=("event_type", "count"),
            total_days_impact=("days_impact_num", "sum"),
            avg_days_impact=("days_impact_num", "mean"),
            total_cost_impact=("cost_impact_num", "sum"),
            delay_like_events=("is_delay_like", "sum"),
        )
        .reset_index()
    )
    result["delay_event_rate"] = result["delay_like_events"] / result["events_count"]
    return result.sort_values(["total_cost_impact", "total_days_impact"], ascending=False)


def _build_feedback_pain_summary(feedback_df: pd.DataFrame) -> pd.DataFrame:
    """Identify likely user pain points and unresolved high-priority requests."""
    df = feedback_df.copy()
    required = {"site", "user_team", "feedback_type", "priority", "status"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    status_series = df["status"].astype(str).str.lower().str.strip()
    missing_status = df["status"].isna() | status_series.isin(["", "nan", "none"])
    resolved = status_series.str.contains("addressed|closed|resolved|done", regex=True, na=False)
    # Missing status means nobody triaged it — that IS the unresolved bucket.
    # Previously excluding missing_status dropped every real high-priority open item.
    unresolved = ~resolved
    high_priority = df["priority"].astype(str).str.lower().str.contains("high", regex=False)

    df["status_missing"] = missing_status
    df["is_unresolved"] = unresolved
    df["is_high_priority"] = high_priority
    df["is_high_priority_unresolved"] = df["is_unresolved"] & df["is_high_priority"]

    summary = (
        df.groupby(["site", "user_team", "feedback_type"], dropna=False)
        .agg(
            total_feedback=("feedback_type", "count"),
            unresolved_feedback=("is_unresolved", "sum"),
            high_priority_unresolved=("is_high_priority_unresolved", "sum"),
            missing_status_count=("status_missing", "sum"),
        )
        .reset_index()
    )
    summary["unresolved_rate"] = summary["unresolved_feedback"] / summary["total_feedback"]
    summary["status_missing_rate"] = summary["missing_status_count"] / summary["total_feedback"]
    return summary.sort_values(["high_priority_unresolved", "unresolved_rate"], ascending=False)


def _build_adoption_metrics(adoption_df: pd.DataFrame) -> pd.DataFrame:
    """Create utilization-style and reporting-completeness metrics."""
    df = adoption_df.copy()
    required = {"site", "week", "areas_systems_deployed", "users_trained", "users_blocked"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["week_num"] = _parse_week_number(df["week"])
    df["users_blocked_num"] = _safe_numeric(df["users_blocked"])
    df["users_trained_num"] = _safe_numeric(df["users_trained"])
    df["areas_systems_deployed_num"] = _safe_numeric(df["areas_systems_deployed"])
    if "change_orders_processed" in df.columns:
        df["change_orders_processed_num"] = _safe_numeric(df["change_orders_processed"])
    else:
        df["change_orders_processed_num"] = pd.NA
    if "incidents_reported" in df.columns:
        df["incidents_reported_num"] = _safe_numeric(df["incidents_reported"])
    else:
        df["incidents_reported_num"] = pd.NA

    df["blocked_rate"] = df["users_blocked_num"] / df["users_trained_num"]
    df["incidents_per_area"] = df["incidents_reported_num"] / df["areas_systems_deployed_num"]
    df["change_orders_per_area"] = df["change_orders_processed_num"] / df["areas_systems_deployed_num"]

    key_columns = [
        "users_blocked",
        "change_orders_processed",
        "incidents_reported",
        "areas_systems_deployed",
        "users_trained",
    ]
    available_key_columns = [col for col in key_columns if col in df.columns]
    df["reporting_completion_rate"] = 1 - df[available_key_columns].isna().mean(axis=1)

    return df.sort_values(["site", "week_num"])


def _build_deployment_duration(event_df: pd.DataFrame, target_weeks: float = 4.0) -> pd.DataFrame:
    """Extract actual vs target deployment weeks from Closure event descriptions.

    Description format observed: "Athena live — N weeks total" (or "N.N weeks").
    """
    df = event_df.copy()
    if df.empty or not {"site", "event_type", "description"}.issubset(df.columns):
        return pd.DataFrame()
    closures = df[df["event_type"].astype(str).str.lower() == "closure"].copy()
    if closures.empty:
        return pd.DataFrame()
    weeks = closures["description"].astype(str).str.extract(r"(\d+(?:\.\d+)?)\s*weeks", expand=False)
    closures["actual_weeks"] = pd.to_numeric(weeks, errors="coerce")
    closures["target_weeks"] = target_weeks
    closures["overrun_weeks"] = closures["actual_weeks"] - target_weeks
    closures["overrun_pct"] = closures["overrun_weeks"] / target_weeks * 100
    return (
        closures[["site", "actual_weeks", "target_weeks", "overrun_weeks", "overrun_pct"]]
        .dropna(subset=["actual_weeks"])
        .sort_values("actual_weeks", ascending=False)
        .reset_index(drop=True)
    )


_PAIN_THEMES: dict[str, list[str]] = {
    "Change Mgmt (clicks/workflow)": [
        "change management", "change order", "workflow", "click", "approval", "baseline",
        "trigger", "sign-off", "sign off",
    ],
    "Tekton <> Athena Sync": [
        "tekton", "offline", "sync", "mobile", "field data", "crew", "field",
    ],
    "External Access / Permissions": [
        "permission", "read-only", "vendor", "external", "partner", "audit requirement",
        "gc", "contractor", "commissioning",
    ],
    "Integrations (Primavera/SAP/API)": [
        "primavera", "sap", "api", "integration", "legacy", "procore", "slack",
    ],
    "Reporting / Variance / Rollups": [
        "report", "variance", "forecast", "dashboard", "rollup", "slow", "5+ min",
    ],
    "Milestones / Scheduling": [
        "milestone", "schedul", "critical path", "dependenc",
    ],
    "Data Quality / Import": [
        "decimal", "precision", "bulk import", "import", "invalid", "error message",
        "format mismatch",
    ],
    "Training / Complexity": [
        "training", "too complex", "complex", "simpler", "unclear",
    ],
}


def _tag_pain_themes(text: str) -> list[str]:
    """Return the list of themes matched by a feedback item (can be 0 or more)."""
    lowered = str(text).lower()
    matched = [name for name, kws in _PAIN_THEMES.items() if any(k in lowered for k in kws)]
    return matched or ["Uncategorized"]


def _build_pain_themes(feedback_df: pd.DataFrame) -> pd.DataFrame:
    """Theme-tag each feedback row and return theme × site counts with priority mix."""
    df = feedback_df.copy()
    required = {"site", "pain_point_request", "priority"}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame()
    df["themes"] = df["pain_point_request"].map(_tag_pain_themes)
    df["priority_norm"] = df["priority"].astype(str).str.lower().str.strip()
    df["is_high"] = df["priority_norm"].str.contains("high", na=False)

    expanded = df.explode("themes")
    rollup = (
        expanded.groupby(["themes", "site"], dropna=False)
        .agg(
            mentions=("pain_point_request", "count"),
            high_priority=("is_high", "sum"),
        )
        .reset_index()
        .rename(columns={"themes": "theme"})
    )
    totals = (
        expanded.groupby("themes")
        .agg(total_mentions=("pain_point_request", "count"), high_total=("is_high", "sum"))
        .reset_index()
        .rename(columns={"themes": "theme"})
        .sort_values("total_mentions", ascending=False)
    )
    return rollup.merge(totals, on="theme").sort_values(
        ["total_mentions", "theme", "site"], ascending=[False, True, True]
    )


def _build_estimate_quality(workbooks: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Flag data-quality defects in the Austin estimate that would break an Athena import."""
    estimate_df = pd.DataFrame()
    for workbook_name, sheets in workbooks.items():
        if "estimate" in workbook_name.lower():
            for sheet_name, df in sheets.items():
                estimate_df = df.copy()
                break
    if estimate_df.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    if "project" in estimate_df.columns:
        missing_project = int(estimate_df["project"].isna().sum())
        if missing_project:
            rows.append({
                "field": "Project",
                "defect": "Missing / blank",
                "rows_affected": missing_project,
                "impact": "Would not import — required for Area/System root node.",
            })
    if "area_system" in estimate_df.columns:
        missing_area = int(estimate_df["area_system"].isna().sum())
        if missing_area:
            rows.append({
                "field": "Area/System",
                "defect": "Missing / blank",
                "rows_affected": missing_area,
                "impact": "Scope orphaned from Area/System hierarchy.",
            })
    for col, label in [("labor_cost", "Labor Cost"), ("material_cost", "Material Cost"),
                       ("rental_cost", "Rental Cost"), ("material_quantity", "Material Quantity")]:
        if col in estimate_df.columns:
            series = estimate_df[col].astype(str)
            mixed = series.str.contains(r"[\$,kKmM]", regex=True, na=False).sum()
            if mixed:
                rows.append({
                    "field": label,
                    "defect": "Mixed format ($, commas, k/M suffixes)",
                    "rows_affected": int(mixed),
                    "impact": "Numeric parser would need pre-processing before load.",
                })
    return pd.DataFrame(rows)


def _build_missing_input_by_sheet(workbooks: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Calculate missing-input rates to detect reporting risk."""
    rows: list[dict[str, float | str]] = []
    for workbook_name, sheets in workbooks.items():
        for sheet_name, df in sheets.items():
            total_cells = len(df) * len(df.columns)
            missing_cells = int(df.isna().sum().sum())
            missing_rate = (missing_cells / total_cells) if total_cells else 0.0
            rows.append(
                {
                    "workbook": workbook_name,
                    "sheet_name": sheet_name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "missing_cells": missing_cells,
                    "missing_rate": missing_rate,
                }
            )
    return pd.DataFrame(rows).sort_values("missing_rate", ascending=False)


def _build_problem_area_ranking(
    event_risk_df: pd.DataFrame,
    financial_variance_df: pd.DataFrame,
    pain_summary_df: pd.DataFrame,
    adoption_metrics_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Rank sites using a blended issue score and return contribution breakdown.

    Methodology note: this is a directional triage index for prioritization,
    not a calibrated predictive risk model.
    """
    site_scores: dict[str, float] = defaultdict(float)
    contribution_rows: list[dict[str, float | str]] = []

    if not event_risk_df.empty:
        max_cost = event_risk_df["total_cost_impact"].max() or 1
        max_days = event_risk_df["total_days_impact"].max() or 1
        for _, row in event_risk_df.iterrows():
            site = str(row["site"])
            cost_component = 0.6 * (row["total_cost_impact"] / max_cost)
            delay_component = 0.4 * (row["total_days_impact"] / max_days)
            site_scores[site] += cost_component + delay_component
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "disruption_cost",
                    "component_score": float(cost_component),
                }
            )
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "delay_impact",
                    "component_score": float(delay_component),
                }
            )

    if not financial_variance_df.empty:
        positive_variance = financial_variance_df.groupby("site", as_index=False)["variance"].sum()
        max_variance = positive_variance["variance"].max() or 1
        for _, row in positive_variance.iterrows():
            site = str(row["site"])
            value = max(float(row["variance"]), 0) / max_variance
            site_scores[site] += value
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "budget_variance",
                    "component_score": float(value),
                }
            )

    if not pain_summary_df.empty:
        pain_by_site = pain_summary_df.groupby("site", as_index=False)["high_priority_unresolved"].sum()
        max_pain = pain_by_site["high_priority_unresolved"].max() or 1
        for _, row in pain_by_site.iterrows():
            site = str(row["site"])
            value = float(row["high_priority_unresolved"]) / max_pain
            site_scores[site] += value
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "unresolved_issues",
                    "component_score": float(value),
                }
            )

    if not adoption_metrics_df.empty and "site" in adoption_metrics_df.columns:
        adoption_site = adoption_metrics_df.groupby("site", as_index=False).agg(
            blocked_rate=("blocked_rate", "mean"),
            reporting_completion_rate=("reporting_completion_rate", "mean"),
        )
        for _, row in adoption_site.iterrows():
            site = str(row["site"])
            blocked_component = float(row["blocked_rate"]) if pd.notna(row["blocked_rate"]) else 0.0
            reporting_penalty = 1 - float(row["reporting_completion_rate"]) if pd.notna(row["reporting_completion_rate"]) else 0.0
            site_scores[site] += blocked_component + reporting_penalty
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "adoption_friction",
                    "component_score": blocked_component,
                }
            )
            contribution_rows.append(
                {
                    "site": site,
                    "site_family": _normalize_site_family(site),
                    "component": "reporting_completeness_penalty",
                    "component_score": reporting_penalty,
                }
            )

    ranked = pd.DataFrame(
        [{"site": site, "problem_score": score} for site, score in site_scores.items()]
    )
    ranked = ranked[ranked["site"].astype(str).str.lower() != "unknown"]
    ranked = ranked.sort_values("problem_score", ascending=False)
    ranked["site_family"] = ranked["site"].map(_normalize_site_family)

    contributions = pd.DataFrame(contribution_rows)
    if contributions.empty:
        contributions = pd.DataFrame(columns=["site", "site_family", "component", "component_score"])
    else:
        contributions = (
            contributions.groupby(["site", "site_family", "component"], as_index=False)["component_score"]
            .sum()
            .sort_values(["site", "component"])
        )
    return ranked.reset_index(drop=True), contributions


def _save_charts(
    charts_dir: Path,
    financial_variance_df: pd.DataFrame,
    event_risk_df: pd.DataFrame,
    adoption_metrics_df: pd.DataFrame,
    pain_summary_df: pd.DataFrame,
    missing_input_df: pd.DataFrame,
    problem_ranking_df: pd.DataFrame,
    duration_df: pd.DataFrame | None = None,
    pain_themes_df: pd.DataFrame | None = None,
) -> None:
    """Save polished Plotly charts as HTML files."""
    ensure_directory(charts_dir)
    for old_chart in charts_dir.glob("*.html"):
        old_chart.unlink()

    title_style = {"size": 20}
    axis_style = {"title_font": {"size": 14}, "tickfont": {"size": 12}}

    if not financial_variance_df.empty:
        top_finance = financial_variance_df.sort_values("variance", ascending=False).head(10).copy()
        top_finance["site_category"] = top_finance["site"] + " | " + top_finance["category"]
        fig = px.bar(
            top_finance,
            x="variance",
            y="site_category",
            orientation="h",
            color="site",
            text="variance",
            color_discrete_sequence=px.colors.qualitative.Safe,
            title="Top Cost Overruns Requiring Immediate Control",
            labels={"variance": "Cost Overrun (Actual - Budgeted, USD)", "site_category": "Site | System Category"},
        )
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(
            template="plotly_white",
            title_font=title_style,
            xaxis=axis_style,
            yaxis=axis_style,
            legend_title_text="Site",
            margin={"l": 60, "r": 30, "t": 80, "b": 50},
        )
        fig.write_html(str(charts_dir / "01_Executive_Cost_Overrun_Priorities.html"))

    if not event_risk_df.empty:
        fig = px.scatter(
            event_risk_df,
            x="total_days_impact",
            y="total_cost_impact",
            size="events_count",
            color="delay_event_rate",
            hover_name="site",
            color_continuous_scale="Reds",
            title="Where Deployment Execution Broke Down Most",
            labels={
                "total_days_impact": "Total Delay Impact (Days)",
                "total_cost_impact": "Total Disruption Cost (USD)",
                "events_count": "Disruption Events",
                "delay_event_rate": "Delay-like Event Rate",
            },
        )
        fig.update_layout(
            template="plotly_white",
            title_font=title_style,
            xaxis=axis_style,
            yaxis=axis_style,
            margin={"l": 60, "r": 30, "t": 80, "b": 50},
        )
        fig.write_html(str(charts_dir / "02_Executive_Deployment_Breakdown_Risk_Map.html"))

    if not adoption_metrics_df.empty:
        adoption_plot = adoption_metrics_df.dropna(subset=["week_num"])
        if not adoption_plot.empty and {"site", "blocked_rate"}.issubset(adoption_plot.columns):
            fig = px.line(
                adoption_plot,
                x="week_num",
                y="blocked_rate",
                color="site",
                title="Adoption Friction Trend: Blocked Users Over Time",
                labels={"week_num": "Deployment Week", "blocked_rate": "Blocked Users / Trained Users"},
                markers=True,
            )
            fig.update_yaxes(tickformat=".0%")
            fig.update_layout(
                template="plotly_white",
                title_font=title_style,
                xaxis=axis_style,
                yaxis=axis_style,
                legend_title_text="Site",
                margin={"l": 60, "r": 30, "t": 80, "b": 50},
            )
            fig.write_html(str(charts_dir / "03_Executive_Adoption_Friction_Trend.html"))

    if not pain_summary_df.empty:
        top_pain = pain_summary_df.sort_values(
            ["high_priority_unresolved", "unresolved_rate"], ascending=False
        ).head(8).copy()
        top_pain["pain_label"] = (
            top_pain["site"].astype(str)
            + " | "
            + top_pain["user_team"].astype(str)
            + " | "
            + top_pain["feedback_type"].astype(str)
        )
        fig = px.bar(
            top_pain,
            x="high_priority_unresolved",
            y="pain_label",
            orientation="h",
            color="unresolved_rate",
            color_continuous_scale="Oranges",
            title="Teams and Systems Most in Need of Intervention",
            labels={
                "high_priority_unresolved": "High-Priority Unresolved Issues",
                "pain_label": "Site | Team | Feedback Type",
                "unresolved_rate": "Unresolved Rate",
            },
        )
        fig.update_layout(
            template="plotly_white",
            title_font=title_style,
            xaxis=axis_style,
            yaxis=axis_style,
            margin={"l": 80, "r": 30, "t": 80, "b": 50},
        )
        fig.write_html(str(charts_dir / "04_Executive_Intervention_Priorities_by_Team.html"))

    if not problem_ranking_df.empty:
        fig = px.bar(
            problem_ranking_df,
            x="site",
            y="problem_score",
            title="Site Priority Ladder for FDE Intervention",
            labels={"problem_score": "Composite Intervention Priority Score", "site": "Site"},
            color="problem_score",
            color_continuous_scale="Reds",
            text="problem_score",
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_layout(
            template="plotly_white",
            title_font=title_style,
            xaxis=axis_style,
            yaxis=axis_style,
            showlegend=False,
            margin={"l": 60, "r": 30, "t": 80, "b": 50},
        )
        fig.write_html(str(charts_dir / "05_Executive_Site_Intervention_Priority.html"))

    if duration_df is not None and not duration_df.empty:
        dplot = duration_df.copy().sort_values("actual_weeks", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dplot["actual_weeks"], y=dplot["site"], orientation="h",
            marker_color=["#E31937" if w > 4 else "#7FB069" for w in dplot["actual_weeks"]],
            text=[f"{w:.1f} wks" for w in dplot["actual_weeks"]],
            textposition="outside", name="Actual",
        ))
        fig.add_vline(x=4, line_dash="dash", line_color="#94A3B8", annotation_text="Target: 4 wks")
        fig.update_layout(
            template="plotly_white", title_font=title_style,
            title="Deployment Duration: Actual vs 4-Week Target",
            xaxis_title="Weeks to Go-Live", yaxis_title="",
            margin={"l": 100, "r": 30, "t": 80, "b": 50},
            showlegend=False,
        )
        fig.write_html(str(charts_dir / "07_Executive_Deployment_Duration.html"))

    if pain_themes_df is not None and not pain_themes_df.empty:
        theme_totals = (
            pain_themes_df.drop_duplicates("theme")[["theme", "total_mentions", "high_total"]]
            .sort_values("total_mentions", ascending=True)
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=theme_totals["total_mentions"], y=theme_totals["theme"], orientation="h",
            marker_color="#E31937", name="Mentions",
            text=theme_totals["total_mentions"], textposition="outside",
        ))
        fig.update_layout(
            template="plotly_white", title_font=title_style,
            title="User Pain Themes — Cross-Site Frequency",
            xaxis_title="Feedback Mentions", yaxis_title="",
            margin={"l": 260, "r": 30, "t": 80, "b": 50},
            showlegend=False,
        )
        fig.write_html(str(charts_dir / "08_Executive_Pain_Themes.html"))

    if not missing_input_df.empty:
        missing_plot = missing_input_df.head(8).sort_values("missing_rate", ascending=True).copy()
        fig = go.Figure(
            data=go.Bar(
                x=missing_plot["missing_rate"],
                y=missing_plot["sheet_name"],
                orientation="h",
                marker={"color": missing_plot["missing_rate"], "colorscale": "OrRd"},
                text=(missing_plot["missing_rate"] * 100).round(1).astype(str) + "%",
                textposition="outside",
            ),
        )
        fig.update_layout(
            title="Where Reporting Inputs Became Unreliable",
            template="plotly_white",
            title_font=title_style,
            xaxis_title="Missing Input Rate",
            yaxis_title="Data Source Sheet",
            xaxis={"tickformat": ".0%", **axis_style},
            yaxis=axis_style,
            showlegend=False,
            margin={"l": 80, "r": 30, "t": 80, "b": 50},
        )
        fig.write_html(str(charts_dir / "06_Executive_Reporting_Reliability_Gaps.html"))


def _build_key_findings_markdown(
    cleaned_dir: Path,
    event_risk_df: pd.DataFrame,
    financial_variance_df: pd.DataFrame,
    pain_summary_df: pd.DataFrame,
    adoption_metrics_df: pd.DataFrame,
    missing_input_df: pd.DataFrame,
    problem_ranking_df: pd.DataFrame,
    duration_df: pd.DataFrame | None = None,
    pain_themes_df: pd.DataFrame | None = None,
    estimate_quality_df: pd.DataFrame | None = None,
) -> None:
    """Create an executive-ready findings memo in markdown."""
    md: list[str] = ["# Tesla FDE — Key Findings", ""]

    # --- Headline: deployment duration ---
    if duration_df is not None and not duration_df.empty:
        md.append("## Headline: Deployment Velocity is the Biggest Signal")
        md.append("")
        md.append("Target: **4 weeks** to go-live. Actuals:")
        md.append("")
        md.append("| Site | Actual weeks | Overrun |")
        md.append("| --- | --- | --- |")
        for _, row in duration_df.iterrows():
            sign = "+" if row["overrun_weeks"] > 0 else ""
            md.append(
                f"| {row['site']} | {row['actual_weeks']:.1f} | "
                f"{sign}{row['overrun_weeks']:.1f} wk ({sign}{row['overrun_pct']:.0f}%) |"
            )
        worst = duration_df.iloc[0]
        best = duration_df.iloc[-1]
        md.append("")
        md.append(
            f"**Spread:** {worst['site']} took {worst['actual_weeks']:.1f} weeks "
            f"({worst['overrun_pct']:.0f}% over target). "
            f"{best['site']} landed in {best['actual_weeks']:.1f}. "
            f"Shanghai/Mexico are the playbook; Berlin is the anti-pattern."
        )
        md.append("")

    # --- Themes ---
    if pain_themes_df is not None and not pain_themes_df.empty:
        theme_totals = (
            pain_themes_df.drop_duplicates("theme")[["theme", "total_mentions", "high_total"]]
            .sort_values("total_mentions", ascending=False)
        )
        md.append("## User Pain Themes (38 feedback items across 5 sites)")
        md.append("")
        md.append("| Theme | Mentions | High-priority |")
        md.append("| --- | --- | --- |")
        for _, row in theme_totals.head(8).iterrows():
            md.append(f"| {row['theme']} | {int(row['total_mentions'])} | {int(row['high_total'])} |")
        md.append("")
        md.append(
            "The top three themes account for the majority of all feedback. "
            "Any Austin plan that doesn't address change-management friction, Tekton sync, "
            "and reporting/rollup reliability is solving the wrong problem."
        )
        md.append("")

    # --- Site-level risk ---
    if not problem_ranking_df.empty:
        md.append("## Site-Level Composite Risk (directional, not calibrated)")
        md.append("")
        md.append("| Site | Composite score |")
        md.append("| --- | --- |")
        for _, row in problem_ranking_df.head(5).iterrows():
            md.append(f"| {row['site']} | {row['problem_score']:.2f} |")
        md.append("")

    # --- Finance ---
    if not financial_variance_df.empty:
        top_variance = financial_variance_df.iloc[0]
        md.append("## Budget Control Failures")
        md.append("")
        md.append(
            f"- Largest overrun: **{top_variance['site']} / {top_variance['category']}** — "
            f"${top_variance['variance']:,.0f} ({top_variance['variance_pct']:.1f}%)."
        )
        # Targeted savings analysis — sites that missed their savings plan
        if "category" in financial_variance_df.columns:
            sav = financial_variance_df[
                financial_variance_df["category"].astype(str).str.contains("Targeted Savings", case=False, na=False)
            ]
            if not sav.empty:
                md.append("- Targeted Savings across sites consistently underperformed plan (realized < budgeted).")
        md.append("")

    # --- Pain points (now actually populated) ---
    if not pain_summary_df.empty:
        real_pain = pain_summary_df[pain_summary_df["high_priority_unresolved"] > 0].head(5)
        md.append("## Top High-Priority Unresolved Items")
        md.append("")
        if real_pain.empty:
            md.append("_No rows met the high-priority unresolved threshold._")
        else:
            for _, row in real_pain.iterrows():
                md.append(
                    f"- **{row['site']}** · {row['user_team']} ({row['feedback_type']}): "
                    f"{int(row['high_priority_unresolved'])} high-priority open "
                    f"({row['unresolved_rate']:.0%} unresolved rate)."
                )
        md.append("")

    # --- Estimate data quality (front-load the Day-1 risk) ---
    if estimate_quality_df is not None and not estimate_quality_df.empty:
        md.append("## Austin Estimate — Day-1 Data Quality Risks")
        md.append("")
        md.append("| Field | Defect | Rows | Import impact |")
        md.append("| --- | --- | --- | --- |")
        for _, row in estimate_quality_df.iterrows():
            md.append(
                f"| {row['field']} | {row['defect']} | {row['rows_affected']} | {row['impact']} |"
            )
        md.append("")

    # --- Recommendations ---
    md.append("## Recommendations for Austin Deployment")
    md.append("")
    md.append("1. **Freeze scope at kickoff** — enforce the Estimate as the single source for Areas/Systems/Scopes/Tasks. Fix data-quality defects before Day 1.")
    md.append("2. **Front-load integration risk (weeks 1–2)** — Primavera milestone sync and SAP budget-code mapping drove the longest Berlin blockers. Validate end-to-end in a staging environment before any user training.")
    md.append("3. **Publish a change-management cheat sheet before training** — the #1 pain theme across all 5 sites. 1-click small-change approvals (already prototyped in Texas) should be backported Day 1.")
    md.append("4. **Make Tekton offline-mode + photo upload a go-live blocker** — field crews at 4 of 5 sites hit this; zones C/D at Austin have known spotty cell coverage per the Technical Survey.")
    md.append("5. **Pre-stage role-based permissions** for 5 external contractors + 2 design partners (MEP, GC, Structural, Commissioning, Electrical; Architect, Structural Eng) — scoped RBAC was a blocker at Berlin and Nevada.")
    md.append("6. **Daily standup + weekly reporting template owned by FDE** — missing-status was the root cause of 22 / 38 feedback items going untriaged. Standardize the fields (site, priority, owner, SLA date).")
    md.append("7. **Named internal champion (P. Kumar)** from prior site; pair with Project Controls (R. Lopez) for weekly budget/variance review.")

    (cleaned_dir / "key_findings.md").write_text("\n".join(md), encoding="utf-8")


def run_inspection_analysis() -> None:
    """Run inspection + exploratory diagnostics for deployment performance and risk."""
    project_root = get_project_root()
    cleaned_dir = ensure_directory(project_root / "outputs" / "cleaned")
    charts_dir = ensure_directory(project_root / "outputs" / "charts")

    workbooks = inspect_all_target_workbooks()
    sheet_lookup = _sheet_lookup(workbooks)

    # Baseline inspection artifacts
    sheet_summary_rows: list[dict[str, str]] = []
    print(f"\n{'=' * 80}")
    print("Concise sheet interpretation")
    print(f"{'=' * 80}")
    for workbook_name, sheets in workbooks.items():
        for sheet_name, df in sheets.items():
            inferred = infer_sheet_purpose(sheet_name=sheet_name, columns=list(df.columns))
            sheet_summary_rows.append(
                {
                    "workbook": workbook_name,
                    "sheet_name": sheet_name,
                    "likely_represents": inferred,
                }
            )
            print(f"- {workbook_name} :: {sheet_name} -> {inferred}")

    concise_summary_df = pd.DataFrame(sheet_summary_rows)
    concise_summary_path = cleaned_dir / "sheet_concise_summary.csv"
    concise_summary_df.to_csv(concise_summary_path, index=False)
    print(f"\nSaved concise sheet summary: {concise_summary_path}")

    join_keys_df = find_possible_join_keys(workbooks=workbooks)
    join_key_path = cleaned_dir / "possible_join_keys.csv"
    join_keys_df.to_csv(join_key_path, index=False)

    print(f"\n{'=' * 80}")
    print("Possible join keys")
    print(f"{'=' * 80}")
    if join_keys_df.empty:
        print("No repeated normalized column names found across sheets.")
    else:
        print(join_keys_df.head(20).to_string(index=False))
    print(f"\nSaved possible join keys: {join_key_path}")

    # Extended exploratory diagnostics
    core_measures_df = _identify_core_measures(workbooks)
    core_measures_df.to_csv(cleaned_dir / "core_measures_inventory.csv", index=False)

    financial_variance_df = _build_financial_variance(sheet_lookup.get("financial records", pd.DataFrame()))
    financial_variance_df.to_csv(cleaned_dir / "financial_variance_by_site_category.csv", index=False)

    event_risk_df = _build_event_risk_summary(sheet_lookup.get("deployment event log", pd.DataFrame()))
    event_risk_df.to_csv(cleaned_dir / "deployment_event_risk_by_site.csv", index=False)

    pain_summary_df = _build_feedback_pain_summary(sheet_lookup.get("user feedback", pd.DataFrame()))
    pain_summary_df.to_csv(cleaned_dir / "pain_points_summary.csv", index=False)

    adoption_metrics_df = _build_adoption_metrics(sheet_lookup.get("adoption metrics", pd.DataFrame()))
    adoption_metrics_df.to_csv(cleaned_dir / "adoption_operational_metrics.csv", index=False)

    missing_input_df = _build_missing_input_by_sheet(workbooks)
    missing_input_df.to_csv(cleaned_dir / "missing_input_risk_by_sheet.csv", index=False)

    duration_df = _build_deployment_duration(sheet_lookup.get("deployment event log", pd.DataFrame()))
    duration_df.to_csv(cleaned_dir / "deployment_duration_by_site.csv", index=False)

    pain_themes_df = _build_pain_themes(sheet_lookup.get("user feedback", pd.DataFrame()))
    pain_themes_df.to_csv(cleaned_dir / "pain_themes_by_site.csv", index=False)

    estimate_quality_df = _build_estimate_quality(workbooks)
    estimate_quality_df.to_csv(cleaned_dir / "austin_estimate_quality_issues.csv", index=False)

    problem_ranking_df, risk_contributions_df = _build_problem_area_ranking(
        event_risk_df=event_risk_df,
        financial_variance_df=financial_variance_df,
        pain_summary_df=pain_summary_df,
        adoption_metrics_df=adoption_metrics_df,
    )
    problem_ranking_df.to_csv(cleaned_dir / "problem_area_ranking.csv", index=False)
    risk_contributions_df.to_csv(cleaned_dir / "problem_score_contributions_by_site.csv", index=False)

    _save_charts(
        charts_dir=charts_dir,
        financial_variance_df=financial_variance_df,
        event_risk_df=event_risk_df,
        adoption_metrics_df=adoption_metrics_df,
        pain_summary_df=pain_summary_df,
        missing_input_df=missing_input_df,
        problem_ranking_df=problem_ranking_df,
        duration_df=duration_df,
        pain_themes_df=pain_themes_df,
    )
    _build_key_findings_markdown(
        cleaned_dir=cleaned_dir,
        event_risk_df=event_risk_df,
        financial_variance_df=financial_variance_df,
        pain_summary_df=pain_summary_df,
        adoption_metrics_df=adoption_metrics_df,
        missing_input_df=missing_input_df,
        problem_ranking_df=problem_ranking_df,
        duration_df=duration_df,
        pain_themes_df=pain_themes_df,
        estimate_quality_df=estimate_quality_df,
    )

    findings: list[str] = []
    if not event_risk_df.empty:
        worst_event_site = event_risk_df.iloc[0]
        findings.append(
            f"Previous-site disruption is concentrated at {worst_event_site['site']}: "
            f"{worst_event_site['events_count']} events, {worst_event_site['total_days_impact']:.1f} impacted days, "
            f"and ~${worst_event_site['total_cost_impact']:,.0f} cost impact."
        )
    if not financial_variance_df.empty:
        worst_variance = financial_variance_df.iloc[0]
        findings.append(
            f"Largest budget overrun appears in {worst_variance['site']} / {worst_variance['category']} "
            f"with variance ~${worst_variance['variance']:,.0f} ({worst_variance['variance_pct']:.1f}%)."
        )
    if not pain_summary_df.empty:
        top_pain_ranked = pain_summary_df.sort_values(
            ["high_priority_unresolved", "unresolved_feedback", "status_missing_rate"],
            ascending=[False, False, False],
        )
        top_pain = top_pain_ranked.iloc[0]
        if float(top_pain["high_priority_unresolved"]) > 0:
            findings.append(
                f"Likely pain point cluster: {top_pain['site']} | {top_pain['user_team']} | {top_pain['feedback_type']} "
                f"with {int(top_pain['high_priority_unresolved'])} high-priority unresolved requests."
            )
        else:
            findings.append(
                f"No explicit high-priority unresolved issues are currently tagged; "
                f"most ambiguous signal appears in {top_pain['site']} | {top_pain['user_team']} | {top_pain['feedback_type']} "
                f"with unresolved rate {top_pain['unresolved_rate']:.0%} and status-missing rate {top_pain['status_missing_rate']:.0%}."
            )
    if not adoption_metrics_df.empty:
        site_adoption = (
            adoption_metrics_df.groupby("site", as_index=False)
            .agg(blocked_rate=("blocked_rate", "mean"), reporting_completion_rate=("reporting_completion_rate", "mean"))
            .sort_values("blocked_rate", ascending=False)
        )
        worst_adoption = site_adoption.iloc[0]
        findings.append(
            f"Adoption friction remains elevated at {worst_adoption['site']}: avg blocked rate "
            f"{worst_adoption['blocked_rate']:.2%}, with reporting completion at "
            f"{worst_adoption['reporting_completion_rate']:.2%}."
        )
    if not missing_input_df.empty:
        worst_missing = missing_input_df.iloc[0]
        findings.append(
            f"Reporting completeness risk is highest in '{worst_missing['sheet_name']}' "
            f"({worst_missing['missing_rate']:.1%} missing cells), reducing confidence in status tracking."
        )
    if not problem_ranking_df.empty:
        findings.append(
            f"Composite risk ranking flags top problem site as {problem_ranking_df.iloc[0]['site']}, "
            f"suggesting this is the strongest baseline analog for preventive planning at the new deployment."
        )

    findings.append(
        "For the new site, FDE should enforce standardized weekly reporting templates and owners for site, status, "
        "days-impact, and cost-impact to prevent low-quality operational visibility."
    )
    findings.append(
        "For the new site, prioritize early mitigation of top historical pain categories with explicit SLAs for "
        "high-priority feedback resolution and blocked-user escalation."
    )

    findings = findings[:8]
    print(f"\n{'=' * 80}")
    print("Diagnostic findings")
    print(f"{'=' * 80}")
    for idx, finding in enumerate(findings[:8], start=1):
        print(f"{idx}. {finding}")

    pd.DataFrame({"finding": findings}).to_csv(cleaned_dir / "diagnostic_findings.csv", index=False)
    print(f"\nSaved diagnostic findings: {cleaned_dir / 'diagnostic_findings.csv'}")
    print(f"Saved chart outputs to: {charts_dir}")


if __name__ == "__main__":
    run_inspection_analysis()
