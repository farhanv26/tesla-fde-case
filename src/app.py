"""Streamlit dashboard for Tesla FDE deployment diagnostics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from analyze import run_inspection_analysis
from utils import get_project_root


st.set_page_config(page_title="Tesla FDE Deployment Dashboard", page_icon=":bar_chart:", layout="wide")

# Presentation-only labels for risk breakdown charts and tables (does not change underlying metrics).
_RISK_SCORE_COMPONENT_LABELS: dict[str, str] = {
    "disruption_cost": "Disruption Cost ($)",
    "delay_impact": "Delay Impact (Days)",
    "budget_variance": "Budget Variance",
    "unresolved_issues": "High-Priority Open Items",
    "adoption_friction": "Blocked User Rate",
    "reporting_completeness_penalty": "Reporting Completeness Penalty",
}


def _inject_styles() -> None:
    """Apply a clean light, presentation-ready style."""
    st.markdown(
        """
        <style>
            :root {
                --bg-main: #F7F9FB;
                --bg-panel: #FFFFFF;
                --bg-card: #FFFFFF;
                --text-primary: #0F172A;
                --text-secondary: #334155;
                --border-soft: #D9E2EC;
                --accent: #2563EB;
                --risk: #DC2626;
            }
            * { font-family: Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
            .stApp { background-color: var(--bg-main); color: var(--text-primary); }
            .stApp [data-testid="stMarkdownContainer"] p,
            .stApp [data-testid="stMarkdownContainer"] li { color: #0F172A; }
            [data-testid="stPlotlyChart"] {
                background-color: #EEF2F7 !important;
                border: 1px solid #D9E2EC !important;
                border-radius: 12px !important;
                padding: 10px 12px 6px 12px !important;
                margin-bottom: 6px !important;
            }
            [data-testid="stPlotlyChart"] .js-plotly-plot .plot-container {
                border-radius: 8px;
            }
            .block-container { padding-top: 0.35rem; padding-bottom: 0.75rem; max-width: 1450px; }
            h1, h2, h3 { color: var(--text-primary); letter-spacing: 0.2px; }
            .main-title { text-align: center; font-size: 2rem; font-weight: 750; color: #0B1733; margin-bottom: 0.25rem; }
            .app-subtitle { color: var(--text-secondary); margin-top: -4px; margin-bottom: 6px; font-size: 0.95rem; text-align: center; }
            .section-header {
                font-size: 1.02rem;
                font-weight: 650;
                color: #13233F;
                padding: 0.4rem 0.2rem;
                border-bottom: 1px solid var(--border-soft);
                margin: 0.45rem 0 0.5rem 0;
            }
            .kpi-card {
                border: 1px solid var(--border-soft);
                border-radius: 12px;
                padding: 14px 16px;
                background: #FFFFFF;
                min-height: 88px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
            }
            .kpi-label { font-size: 0.82rem; color: #475569; margin-bottom: 6px; letter-spacing: 0.15px; }
            .kpi-value { font-size: 1.78rem; font-weight: 760; color: #0F172A; line-height: 1.1; }
            [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid var(--border-soft); }
            [data-testid="stSidebar"] .block-container { padding-top: 0.8rem; }
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #1E293B !important; }
            [data-testid="stSidebar"] .stMultiSelect, [data-testid="stSidebar"] .stSlider {
                margin-bottom: 0.45rem;
            }
            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] [data-baseweb="input"] input {
                background-color: #FFFFFF !important;
                color: #0F172A !important;
                border: 1px solid #CBD5E1 !important;
                border-radius: 8px !important;
            }
            [data-testid="stSidebar"] [data-baseweb="select"] svg,
            [data-testid="stSidebar"] [data-baseweb="select"] path,
            [data-testid="stSidebar"] [data-baseweb="popover"] svg,
            [data-testid="stSidebar"] [data-baseweb="popover"] path {
                fill: #0F172A !important;
                color: #0F172A !important;
                opacity: 1 !important;
            }
            div[data-baseweb="popover"],
            ul[role="listbox"],
            li[role="option"] {
                background-color: #FFFFFF !important;
                color: #0F172A !important;
                border: 1px solid #E2E8F0 !important;
                box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08) !important;
            }
            li[role="option"]:hover,
            li[role="option"][aria-selected="true"] {
                background-color: #EFF6FF !important;
                color: #0F172A !important;
            }
            [data-testid="stSidebar"] .stSlider label { color: #1E293B !important; font-weight: 500 !important; }
            [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] { background-color: #E2E8F0 !important; }
            [data-testid="stDataFrame"] {
                border: 1px solid var(--border-soft);
                border-radius: 10px;
                overflow: hidden;
                background-color: #FFFFFF !important;
            }
            [data-testid="stDataFrame"] [data-testid="stStyledTable"] {
                background-color: #FFFFFF !important;
            }
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"],
            header[data-testid="stHeader"],
            #MainMenu,
            footer {
                display: none !important;
            }
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
        "risk_contrib": _read_csv_if_exists(cleaned_dir / "problem_score_contributions_by_site.csv"),
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


def _apply_light_chart(
    fig,
    *,
    title: str,
    legend_below: bool = False,
    extra_right: int = 0,
    extra_left: int = 0,
) -> None:
    """Light theme + high-contrast text for screenshots; does not change data."""
    legend_config = (
        {
            "font": {"size": 13, "color": "#0F172A"},
            "bgcolor": "rgba(255,255,255,0.97)",
            "bordercolor": "#E2E8F0",
            "borderwidth": 1,
            "orientation": "h",
            "y": -0.32,
            "yanchor": "top",
            "x": 0.5,
            "xanchor": "center",
        }
        if legend_below
        else {
            "font": {"size": 13, "color": "#0F172A"},
            "bgcolor": "rgba(255,255,255,0.97)",
            "bordercolor": "#E2E8F0",
            "borderwidth": 1,
        }
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FAFBFD",
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 20, "color": "#0F172A"},
        },
        font={"color": "#0F172A", "size": 14},
        margin={
            "l": 48 + extra_left,
            "r": 44 + extra_right,
            "t": 64,
            "b": 118 if legend_below else 56,
        },
        legend_title_text="",
        legend=legend_config,
        height=305,
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E8EDF3",
        zeroline=False,
        linecolor="#94A3B8",
        title_font={"size": 15, "color": "#0F172A"},
        tickfont={"size": 12, "color": "#334155"},
        mirror=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E8EDF3",
        zeroline=False,
        linecolor="#94A3B8",
        title_font={"size": 15, "color": "#0F172A"},
        tickfont={"size": 12, "color": "#334155"},
        mirror=False,
    )


def _style_colorbar(fig, *, title: str) -> None:
    """Readable colorbar for continuous scales (delay rate, etc.)."""
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text=title, font=dict(size=14, color="#0F172A")),
            tickfont=dict(size=12, color="#334155"),
            outlinecolor="#CBD5E1",
            outlinewidth=1,
            bgcolor="#FFFFFF",
        )
    )


def _light_table_styles() -> list[dict]:
    """Light, presentation-friendly table chrome (used with pandas Styler)."""
    return [
        {"selector": "th", "props": [
            ("background-color", "#E8EEF4"),
            ("color", "#0F172A"),
            ("font-weight", "650"),
            ("font-size", "13px"),
            ("border", "1px solid #E2E8F0"),
            ("padding", "10px 12px"),
            ("text-align", "left"),
        ]},
        {"selector": "td", "props": [
            ("background-color", "#FFFFFF"),
            ("color", "#0F172A"),
            ("font-size", "13px"),
            ("border", "1px solid #E8EDF3"),
            ("padding", "8px 12px"),
        ]},
        {"selector": "table", "props": [
            ("border-collapse", "collapse"),
            ("background-color", "#FFFFFF"),
        ]},
    ]


def _style_top_risk_sites_table(table_df: pd.DataFrame):
    """White base table; subtle heat only on the priority column."""
    heat_col = "Review Priority Index"
    fmt = {
        "Disruption Cost ($)": "${:,.0f}",
        "Delay Impact (Days)": "{:.1f}",
        "Budget Variance ($)": "${:,.0f}",
        heat_col: "{:.2f}",
    }
    base_cols = [c for c in table_df.columns if c != heat_col]
    pi_min = float(table_df[heat_col].min())
    pi_max = float(table_df[heat_col].max())
    return (
        table_df.style.format(fmt)
        .set_properties(subset=base_cols, **{"background-color": "#FFFFFF", "color": "#0F172A"})
        .background_gradient(subset=[heat_col], cmap="YlOrBr", vmin=pi_min, vmax=pi_max)
        .set_table_styles(_light_table_styles())
    )


def _style_risk_breakdown_table(contrib_rounded: pd.DataFrame, *, total_col: str = "Composite Risk Score"):
    """Component columns stay neutral; heat only on the total column."""
    id_cols = ("Site", "Site Family")
    numeric_cols = [c for c in contrib_rounded.columns if c not in id_cols]
    fmt_dict = {c: "{:.2f}" for c in numeric_cols}
    neutral_cols = [c for c in contrib_rounded.columns if c != total_col]
    ts_min = float(contrib_rounded[total_col].min()) if not contrib_rounded.empty else 0.0
    ts_max = float(contrib_rounded[total_col].max()) if not contrib_rounded.empty else 1.0
    return (
        contrib_rounded.style.format(fmt_dict)
        .set_properties(subset=neutral_cols, **{"background-color": "#FFFFFF", "color": "#0F172A"})
        .background_gradient(subset=[total_col], cmap="YlOrBr", vmin=ts_min, vmax=ts_max)
        .set_table_styles(_light_table_styles())
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

    st.sidebar.markdown("### Filters")
    selected_sites = st.sidebar.multiselect("Site", options=sorted(site_values))
    selected_teams = st.sidebar.multiselect("Team", options=team_values)
    selected_systems = st.sidebar.multiselect("System Category", options=system_values)
    selected_week_range = st.sidebar.slider(
        "Week Range",
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
        if sites and name == "risk_contrib" and "site" in result.columns:
            result = result[result["site"].astype(str).isin(sites)]
        if name == "adoption" and "week_num" in result.columns:
            result["week_num"] = pd.to_numeric(result["week_num"], errors="coerce")
            result = result[result["week_num"].between(float(week_low), float(week_high), inclusive="both")]
        filtered[name] = result
    return filtered


def main() -> None:
    """Run Streamlit app."""
    _inject_styles()
    st.markdown("<div class='main-title'>Tesla FDE Deployment Monitoring Dashboard</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='app-subtitle'>Deployment performance, intervention priority, and explainable site ranking.</div>",
        unsafe_allow_html=True,
    )

    root = get_project_root()
    cleaned_dir = root / "outputs" / "cleaned"
    data = _ensure_data_ready(cleaned_dir)

    filters = _build_sidebar_filters(data)
    filtered = _apply_filters(data, filters)

    st.markdown("<div class='section-header'>Key Metrics</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="medium")

    total_disruption_cost = filtered["events"]["total_cost_impact"].sum() if not filtered["events"].empty else 0
    avg_blocked_rate = filtered["adoption"]["blocked_rate"].mean() if not filtered["adoption"].empty else 0
    high_priority_open = (
        filtered["pain"]["high_priority_unresolved"].sum() if not filtered["pain"].empty else 0
    )
    top_score = filtered["ranking"]["problem_score"].max() if not filtered["ranking"].empty else 0

    with c1:
        _kpi_card("Total disruption cost", f"${total_disruption_cost:,.0f}")
    with c2:
        _kpi_card("Avg. blocked-user rate", f"{avg_blocked_rate:.1%}")
    with c3:
        _kpi_card("High-priority open (count)", f"{int(high_priority_open)}")
    with c4:
        _kpi_card("Highest composite risk score", f"{top_score:.2f}")

    st.markdown("<div class='section-header'>Where deployment performance broke down</div>", unsafe_allow_html=True)
    col_left, col_right = st.columns(2, gap="medium")

    with col_left:
        if not filtered["events"].empty:
            fig_events = px.scatter(
                filtered["events"],
                x="total_days_impact",
                y="total_cost_impact",
                size="events_count",
                color="delay_event_rate",
                hover_name="site",
                color_continuous_scale="YlOrRd",
                title="",
                labels={
                    "total_days_impact": "Total delay impact (days)",
                    "total_cost_impact": "Total disruption cost ($)",
                    "delay_event_rate": "Delay-like share of events",
                },
            )
            fig_events.update_traces(marker=dict(line=dict(width=0.5, color="#FFFFFF")))
            _apply_light_chart(
                fig_events, title="Delays vs. cost impact by site", legend_below=False, extra_right=32
            )
            _style_colorbar(fig_events, title="Delay-like share")
            st.plotly_chart(fig_events, use_container_width=True)
        else:
            st.info("No deployment event data for current filters.")

    with col_right:
        if not filtered["ranking"].empty:
            ranking_plot = filtered["ranking"].sort_values("problem_score", ascending=False).head(10)
            fig_rank = px.bar(
                ranking_plot,
                x="problem_score",
                y="site",
                orientation="h",
                title="",
                labels={"problem_score": "Composite score (directional)", "site": "Site"},
                color="problem_score",
                color_continuous_scale="OrRd",
            )
            fig_rank.update_traces(marker_line_width=0)
            _apply_light_chart(
                fig_rank, title="Site risk prioritization", legend_below=False, extra_right=28, extra_left=24
            )
            _style_colorbar(fig_rank, title="Composite score")
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("No ranking data for current filters.")

    st.markdown("<div class='section-header'>Where to prioritize intervention</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2, gap="medium")

    with col_a:
        if not filtered["pain"].empty:
            pain_base = filtered["pain"].copy()
            hp_max = pd.to_numeric(pain_base["high_priority_unresolved"], errors="coerce").max()
            if pd.isna(hp_max):
                hp_max = 0.0
            use_hp_bars = float(hp_max) >= 2.0
            if use_hp_bars:
                pain_plot = pain_base.sort_values(
                    ["high_priority_unresolved", "unresolved_rate"], ascending=False
                ).head(12)
            else:
                pain_plot = pain_base.sort_values(
                    ["unresolved_feedback", "unresolved_rate"], ascending=False
                ).head(12)
            pain_plot = pain_plot.assign(
                team_label=pain_plot["site"].astype(str) + " · " + pain_plot["user_team"].astype(str)
            )
            if use_hp_bars:
                fig_pain = px.bar(
                    pain_plot,
                    x="high_priority_unresolved",
                    y="team_label",
                    orientation="h",
                    title="",
                    labels={
                        "high_priority_unresolved": "Count (high-priority, unresolved)",
                        "team_label": "Site · team",
                    },
                    color="unresolved_rate",
                    color_continuous_scale="YlOrRd",
                )
                pain_title = "High-priority open backlog by site and team"
                cbar_title = "Share unresolved"
            else:
                fig_pain = px.bar(
                    pain_plot,
                    x="unresolved_feedback",
                    y="team_label",
                    orientation="h",
                    title="",
                    labels={
                        "unresolved_feedback": "Unresolved items",
                        "team_label": "Site · team",
                    },
                    color="unresolved_rate",
                    color_continuous_scale="YlOrRd",
                )
                pain_title = "Role-based coordination friction"
                cbar_title = "Share unresolved"
            fig_pain.update_traces(marker_line_width=0)
            _apply_light_chart(fig_pain, title=pain_title, legend_below=False, extra_right=28, extra_left=96)
            _style_colorbar(fig_pain, title=cbar_title)
            st.plotly_chart(fig_pain, use_container_width=True)
        else:
            st.info("No feedback data for current filters.")

    with col_b:
        if not filtered["adoption"].empty:
            adoption_plot = filtered["adoption"].dropna(subset=["week_num"]).copy()
            if not adoption_plot.empty:
                fig_adoption = px.line(
                    adoption_plot,
                    x="week_num",
                    y="blocked_rate",
                    color="site",
                    markers=True,
                    title="",
                    labels={"week_num": "Week #", "blocked_rate": "Blocked / trained users"},
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_adoption.update_yaxes(tickformat=".0%")
                _apply_light_chart(
                    fig_adoption,
                    title="Adoption friction over time by site",
                    legend_below=True,
                )
                st.plotly_chart(fig_adoption, use_container_width=True)
            else:
                st.info("No week-level adoption rows for current filters.")
        else:
            st.info("No adoption data for current filters.")

    st.markdown("<div class='section-header'>Sites to prioritize for review</div>", unsafe_allow_html=True)
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
                "total_cost_impact": "Disruption Cost ($)",
                "total_days_impact": "Delay Impact (Days)",
                "variance": "Budget Variance ($)",
                "priority_index": "Review Priority Index",
            }
        )
        table_df = table_df.round(
            {
                "Disruption Cost ($)": 0,
                "Delay Impact (Days)": 1,
                "Budget Variance ($)": 0,
                "Review Priority Index": 2,
            }
        )
        styled_table = _style_top_risk_sites_table(table_df)
        st.dataframe(styled_table, use_container_width=True, hide_index=True)
    else:
        st.info("Risk table unavailable for current filters.")

    st.markdown("<div class='section-header'>Why site ranking is explainable</div>", unsafe_allow_html=True)
    if not filtered["risk_contrib"].empty:
        contrib = filtered["risk_contrib"].copy()
        contrib["component_label"] = contrib["component"].map(_RISK_SCORE_COMPONENT_LABELS).fillna(
            contrib["component"].astype(str)
        )
        contrib_plot = contrib.merge(
            filtered["ranking"][["site", "problem_score"]],
            on="site",
            how="left",
        ).sort_values("problem_score", ascending=False)

        fig_contrib = px.bar(
            contrib_plot,
            x="site",
            y="component_score",
            color="component_label",
            title="",
            barmode="stack",
            labels={
                "site": "Site",
                "component_score": "Score contribution",
                "component_label": "Factor",
            },
            color_discrete_map={
                "Disruption Cost ($)": "#EA580C",
                "Delay Impact (Days)": "#F97316",
                "Budget Variance": "#F59E0B",
                "High-Priority Open Items": "#DC2626",
                "Blocked User Rate": "#2563EB",
                "Reporting Completeness Penalty": "#64748B",
            },
        )
        fig_contrib.update_traces(marker_line_width=0)
        fig_contrib.update_layout(bargap=0.28)
        _apply_light_chart(
            fig_contrib,
            title="Drivers of site risk score",
            legend_below=True,
        )
        fig_contrib.update_xaxes(categoryorder="array", categoryarray=contrib_plot["site"].drop_duplicates().tolist())
        st.plotly_chart(fig_contrib, use_container_width=True)

        contrib_table = (
            contrib.pivot_table(
                index=["site", "site_family"],
                columns="component_label",
                values="component_score",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .merge(filtered["ranking"][["site", "problem_score"]], on="site", how="left")
            .sort_values("problem_score", ascending=False)
            .rename(
                columns={
                    "site": "Site",
                    "site_family": "Site Family",
                    "problem_score": "Composite Risk Score",
                }
            )
        )
        numeric_cols = [c for c in contrib_table.columns if c not in ("Site", "Site Family")]
        round_spec = {c: 2 for c in numeric_cols}
        contrib_rounded = contrib_table.round(round_spec)
        contrib_styled = _style_risk_breakdown_table(contrib_rounded, total_col="Composite Risk Score")
        st.dataframe(contrib_styled, use_container_width=True, hide_index=True)
    else:
        st.info("Risk score breakdown is unavailable for current filters.")


if __name__ == "__main__":
    main()
