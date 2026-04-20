"""Streamlit dashboard for Tesla FDE deployment diagnostics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from analyze import run_inspection_analysis
from utils import get_project_root


st.set_page_config(page_title="Tesla FDE Deployment Dashboard", page_icon=":bar_chart:", layout="wide")


def _inject_styles() -> None:
    """Apply a lightweight dark, presentation-ready style."""
    st.markdown(
        """
        <style>
            .stApp { background-color: #0F172A; color: #E2E8F0; }
            .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }
            h1, h2, h3 { color: #F8FAFC; }
            .kpi-card {
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 14px;
                background: #111827;
            }
            .kpi-label { font-size: 0.85rem; color: #94A3B8; margin-bottom: 6px; }
            .kpi-value { font-size: 1.55rem; font-weight: 700; color: #F8FAFC; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    """Load CSV if available; return empty dataframe otherwise."""
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _load_cleaned_data(cleaned_dir: Path) -> dict[str, pd.DataFrame]:
    """Load dashboard datasets from outputs/cleaned."""
    return {
        "ranking": _read_csv_if_exists(cleaned_dir / "problem_area_ranking.csv"),
        "events": _read_csv_if_exists(cleaned_dir / "deployment_event_risk_by_site.csv"),
        "pain": _read_csv_if_exists(cleaned_dir / "pain_points_summary.csv"),
        "adoption": _read_csv_if_exists(cleaned_dir / "adoption_operational_metrics.csv"),
        "finance": _read_csv_if_exists(cleaned_dir / "financial_variance_by_site_category.csv"),
        "missing": _read_csv_if_exists(cleaned_dir / "missing_input_risk_by_sheet.csv"),
    }


def _ensure_data_ready(cleaned_dir: Path) -> dict[str, pd.DataFrame]:
    """
    Ensure cleaned outputs exist.

    Falls back to running analysis when cleaned artifacts are missing.
    """
    data = _load_cleaned_data(cleaned_dir)
    if any(df.empty for df in data.values()):
        with st.spinner("Preparing cleaned diagnostics from source workbooks..."):
            run_inspection_analysis()
        data = _load_cleaned_data(cleaned_dir)
    return data


def _kpi_card(label: str, value: str) -> None:
    """Render one KPI card."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_sidebar_filters(data: dict[str, pd.DataFrame]) -> dict[str, list[str] | tuple[float, float]]:
    """Build sidebar filters from dimensions that exist in cleaned data."""
    site_values: set[str] = set()
    for key in ("events", "pain", "adoption", "finance", "ranking"):
        df = data[key]
        if not df.empty and "site" in df.columns:
            site_values.update(df["site"].dropna().astype(str).unique().tolist())

    team_values: list[str] = []
    if not data["pain"].empty and "user_team" in data["pain"].columns:
        team_values = sorted(data["pain"]["user_team"].dropna().astype(str).unique().tolist())

    system_values: list[str] = []
    if not data["finance"].empty and "category" in data["finance"].columns:
        system_values = sorted(data["finance"]["category"].dropna().astype(str).unique().tolist())

    week_bounds = (1.0, 12.0)
    if not data["adoption"].empty and "week_num" in data["adoption"].columns:
        week_num = pd.to_numeric(data["adoption"]["week_num"], errors="coerce").dropna()
        if not week_num.empty:
            week_bounds = (float(week_num.min()), float(week_num.max()))

    st.sidebar.header("Filters")
    selected_sites = st.sidebar.multiselect("Site", options=sorted(site_values))
    selected_teams = st.sidebar.multiselect("Team", options=team_values)
    selected_systems = st.sidebar.multiselect("System Category", options=system_values)
    selected_week_range = st.sidebar.slider(
        "Time Period (Week Number)",
        min_value=float(week_bounds[0]),
        max_value=float(week_bounds[1]),
        value=(float(week_bounds[0]), float(week_bounds[1])),
        step=1.0,
    )

    return {
        "sites": selected_sites,
        "teams": selected_teams,
        "systems": selected_systems,
        "week_range": selected_week_range,
    }


def _apply_filters(data: dict[str, pd.DataFrame], filters: dict[str, list[str] | tuple[float, float]]) -> dict[str, pd.DataFrame]:
    """Apply shared sidebar filters to each dataset."""
    sites = filters["sites"]
    teams = filters["teams"]
    systems = filters["systems"]
    week_low, week_high = filters["week_range"]

    filtered: dict[str, pd.DataFrame] = {}
    for name, df in data.items():
        if df.empty:
            filtered[name] = df
            continue
        result = df.copy()
        if sites and "site" in result.columns:
            result = result[result["site"].astype(str).isin(sites)]
        if teams and name == "pain" and "user_team" in result.columns:
            result = result[result["user_team"].astype(str).isin(teams)]
        if systems and name == "finance" and "category" in result.columns:
            result = result[result["category"].astype(str).isin(systems)]
        if name == "adoption" and "week_num" in result.columns:
            result["week_num"] = pd.to_numeric(result["week_num"], errors="coerce")
            result = result[result["week_num"].between(float(week_low), float(week_high), inclusive="both")]
        filtered[name] = result
    return filtered


def main() -> None:
    """Run Streamlit app."""
    _inject_styles()
    st.title("Tesla FDE Deployment Monitoring Dashboard")
    st.caption("Decision-focused view for Forward Deploy Engineers, PMs, and Project Controls.")

    root = get_project_root()
    cleaned_dir = root / "outputs" / "cleaned"
    data = _ensure_data_ready(cleaned_dir)

    filters = _build_sidebar_filters(data)
    filtered = _apply_filters(data, filters)

    st.header("Executive KPI Snapshot")
    c1, c2, c3, c4 = st.columns(4)

    total_disruption_cost = filtered["events"]["total_cost_impact"].sum() if not filtered["events"].empty else 0
    avg_blocked_rate = filtered["adoption"]["blocked_rate"].mean() if not filtered["adoption"].empty else 0
    high_priority_open = (
        filtered["pain"]["high_priority_unresolved"].sum() if not filtered["pain"].empty else 0
    )
    top_score = filtered["ranking"]["problem_score"].max() if not filtered["ranking"].empty else 0

    with c1:
        _kpi_card("Total Disruption Cost Impact", f"${total_disruption_cost:,.0f}")
    with c2:
        _kpi_card("Average Blocked-User Rate", f"{avg_blocked_rate:.1%}")
    with c3:
        _kpi_card("High-Priority Unresolved Issues", f"{int(high_priority_open)}")
    with c4:
        _kpi_card("Top Composite Risk Score", f"{top_score:.2f}")

    st.header("Where Deployment Broke Down")
    col_left, col_right = st.columns(2)

    with col_left:
        if not filtered["events"].empty:
            # Easy label swap: update title/labels below for presentation wording.
            fig_events = px.scatter(
                filtered["events"],
                x="total_days_impact",
                y="total_cost_impact",
                size="events_count",
                color="delay_event_rate",
                hover_name="site",
                color_continuous_scale="Reds",
                title="Deployment Breakdown Risk Map",
                labels={
                    "total_days_impact": "Delay Impact (Days)",
                    "total_cost_impact": "Disruption Cost (USD)",
                    "delay_event_rate": "Delay-like Event Rate",
                },
            )
            fig_events.update_layout(template="plotly_dark", margin={"l": 20, "r": 20, "t": 55, "b": 20})
            st.plotly_chart(fig_events, use_container_width=True)
        else:
            st.info("No deployment event data available for current filters.")

    with col_right:
        if not filtered["ranking"].empty:
            ranking_plot = filtered["ranking"].sort_values("problem_score", ascending=False).head(10)
            # Easy label swap: update title/axis labels below as needed.
            fig_rank = px.bar(
                ranking_plot,
                x="problem_score",
                y="site",
                orientation="h",
                title="Site Intervention Priority Ranking",
                labels={"problem_score": "Composite Risk Score", "site": "Site"},
                color="problem_score",
                color_continuous_scale="OrRd",
            )
            fig_rank.update_layout(template="plotly_dark", margin={"l": 20, "r": 20, "t": 55, "b": 20})
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("No ranking data available for current filters.")

    st.header("What Needs Intervention First")
    col_a, col_b = st.columns(2)

    with col_a:
        if not filtered["pain"].empty:
            pain_plot = filtered["pain"].sort_values(
                ["high_priority_unresolved", "unresolved_rate"], ascending=False
            ).head(12)
            pain_plot = pain_plot.assign(
                team_label=pain_plot["site"].astype(str) + " | " + pain_plot["user_team"].astype(str)
            )
            # Easy label swap: update title/labels for audience language.
            fig_pain = px.bar(
                pain_plot,
                x="high_priority_unresolved",
                y="team_label",
                orientation="h",
                title="Teams with Highest Unresolved Critical Issues",
                labels={
                    "high_priority_unresolved": "High-Priority Unresolved",
                    "team_label": "Site | Team",
                },
                color="unresolved_rate",
                color_continuous_scale="YlOrRd",
            )
            fig_pain.update_layout(template="plotly_dark", margin={"l": 20, "r": 20, "t": 55, "b": 20})
            st.plotly_chart(fig_pain, use_container_width=True)
        else:
            st.info("No pain-point data available for current filters.")

    with col_b:
        if not filtered["adoption"].empty:
            adoption_plot = filtered["adoption"].dropna(subset=["week_num"]).copy()
            if not adoption_plot.empty:
                # Easy label swap: update title/labels below for slide consistency.
                fig_adoption = px.line(
                    adoption_plot,
                    x="week_num",
                    y="blocked_rate",
                    color="site",
                    markers=True,
                    title="Adoption Friction Trend by Week",
                    labels={"week_num": "Week", "blocked_rate": "Blocked Users / Trained Users"},
                )
                fig_adoption.update_yaxes(tickformat=".0%")
                fig_adoption.update_layout(template="plotly_dark", margin={"l": 20, "r": 20, "t": 55, "b": 20})
                st.plotly_chart(fig_adoption, use_container_width=True)
            else:
                st.info("No adoption trend rows available for current filters.")
        else:
            st.info("No adoption data available for current filters.")

    st.header("Top Risk Areas Table")
    if not filtered["finance"].empty and not filtered["events"].empty:
        event_site = filtered["events"][["site", "total_cost_impact", "total_days_impact"]].copy()
        finance_site = filtered["finance"].groupby("site", as_index=False)["variance"].sum()
        table_df = event_site.merge(finance_site, on="site", how="outer").fillna(0)
        table_df["priority_index"] = (
            table_df["total_cost_impact"].rank(pct=True)
            + table_df["total_days_impact"].rank(pct=True)
            + table_df["variance"].rank(pct=True)
        )
        table_df = table_df.sort_values("priority_index", ascending=False).head(10)
        table_df = table_df.rename(
            columns={
                "site": "Site",
                "total_cost_impact": "Disruption Cost Impact",
                "total_days_impact": "Delay Days Impact",
                "variance": "Budget Variance",
                "priority_index": "Priority Index",
            }
        )
        st.dataframe(table_df, use_container_width=True, hide_index=True)
    else:
        st.info("Risk table unavailable for current filters.")


if __name__ == "__main__":
    main()
