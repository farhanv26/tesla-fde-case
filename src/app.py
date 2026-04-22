"""Streamlit dashboard for Tesla FDE deployment diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyze import run_inspection_analysis
from utils import get_project_root


st.set_page_config(page_title="Tesla FDE Deployment Dashboard", page_icon=":bar_chart:", layout="wide")


_RISK_SCORE_COMPONENT_LABELS: dict[str, str] = {
    "disruption_cost": "Disruption Cost ($)",
    "delay_impact": "Delay Impact (Days)",
    "budget_variance": "Budget Variance",
    "unresolved_issues": "High-Priority Open Items",
    "adoption_friction": "Blocked User Rate",
    "reporting_completeness_penalty": "Reporting Completeness Penalty",
}

_MAIN_DRIVER_SUMMARY: dict[str, str] = {
    "disruption_cost": "Disruption-driven cost pressure",
    "delay_impact": "Schedule delays and slip",
    "budget_variance": "Budget variance / controls",
    "unresolved_issues": "Unresolved high-priority feedback",
    "adoption_friction": "Adoption friction (blocked users)",
    "reporting_completeness_penalty": "Reporting gaps",
}

_ACTION_STRIP_SHORT: dict[str, str] = {
    "disruption_cost": "Daily impact huddle + owners",
    "delay_impact": "Daily PM review + schedule recovery",
    "budget_variance": "Estimate vs. actual + change control",
    "unresolved_issues": "Triage cadence + named owners",
    "adoption_friction": "Targeted onboarding + unblock list",
    "reporting_completeness_penalty": "Lock weekly reporting + sign-off",
}

_FOCUS_COLOR = "#E31937"          # Tesla red
_MUTED_COLOR = "#606060"          # mid gray for non-focused series on dark bg
_TEXT_PRIMARY = "#F5F5F5"
_TEXT_SECONDARY = "#A0A0A0"
_BG_PAGE = "#0A0A0A"
_BG_CARD = "#151515"
_BORDER = "#262626"
_GOOD = "#7FB069"                 # under-target green (used for duration bars)

_PLOTLY_CONFIG: dict = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
}

# Session state keys (centralized so nothing is misspelled across callers).
_SS_CLICK = "fde_clicked_site"
_SS_PREV_SIDEBAR = "fde_prev_sidebar_sites"


@dataclass(frozen=True)
class FocusState:
    """Single source of truth for narrative + highlights vs. filters."""

    mode: Literal["portfolio", "single", "multi"]
    selected_sites: tuple[str, ...]
    focus_site: str
    focus_score: float
    source: Literal["click", "sidebar_single", "sidebar_multi", "auto", "portfolio", "none"]


def _inject_styles() -> None:
    """Tesla-themed dark presentation surface."""
    st.markdown(
        """
        <style>
            :root {
                --bg-page: #0A0A0A;
                --bg-card: #151515;
                --bg-elev: #1E1E1E;
                --border: #262626;
                --border-strong: #3A3A3A;
                --text-primary: #F5F5F5;
                --text-secondary: #A0A0A0;
                --text-dim: #707070;
                --accent: #E31937;
                --accent-dim: #8E0F1F;
                --ok: #7FB069;
            }
            * { font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif; }
            .stApp { background-color: var(--bg-page); color: var(--text-primary); }
            .stApp, [data-testid="stAppViewContainer"] { color-scheme: dark; }
            .stApp [data-testid="stMarkdownContainer"] p,
            .stApp [data-testid="stMarkdownContainer"] li,
            .stApp [data-testid="stMarkdownContainer"] strong,
            .stApp [data-testid="stMarkdownContainer"] b { color: var(--text-primary); }
            .block-container { padding-top: 0.75rem; padding-bottom: 1rem; max-width: 1480px; }
            h1, h2, h3 { color: var(--text-primary); letter-spacing: 0.2px; font-weight: 600; }

            .brand-row {
                display: flex; align-items: center; justify-content: space-between;
                padding: 2px 4px 10px 4px;
                border-bottom: 1px solid var(--border);
                margin-bottom: 14px;
            }
            .brand-left {
                display: flex; align-items: center; gap: 14px;
            }
            .brand-mark {
                font-size: 1.35rem; font-weight: 800; letter-spacing: 0.32em;
                color: var(--accent);
            }
            .brand-pipe {
                width: 1px; height: 28px; background: var(--border-strong);
            }
            .brand-product {
                font-size: 0.95rem; font-weight: 600;
                color: var(--text-primary); letter-spacing: 0.02em;
            }
            .brand-product .muted { color: var(--text-secondary); font-weight: 400; }
            .brand-right {
                font-size: 0.72rem; color: var(--text-dim);
                letter-spacing: 0.14em; text-transform: uppercase;
            }

            .mode-label {
                text-align: left;
                margin: 2px 0 8px 0;
                font-size: 0.72rem;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                font-weight: 600;
                color: var(--text-secondary);
            }
            .mode-label .pill {
                display: inline-block;
                padding: 3px 11px;
                border-radius: 2px;
                color: #FFFFFF;
                background: var(--border-strong);
                letter-spacing: 0.12em;
                font-size: 0.68rem;
                margin-right: 10px;
            }
            .mode-label.deepdive .pill { background: var(--accent); }
            .mode-label .site { color: var(--accent); font-weight: 700; letter-spacing: 0.04em; text-transform: none; }

            .section-header {
                font-size: 0.72rem; font-weight: 600;
                color: var(--text-secondary);
                letter-spacing: 0.22em;
                text-transform: uppercase;
                padding: 0.4rem 0.2rem 0.3rem 0.2rem;
                border-bottom: 1px solid var(--border);
                margin: 0.95rem 0 0.55rem 0;
            }
            .hint { color: var(--text-dim); font-size: 0.76rem; margin: 0 0 10px 2px; }

            .focus-banner {
                display: flex; align-items: center; gap: 14px;
                border-radius: 4px; padding: 12px 16px;
                margin: 0.2rem 0 0.55rem 0;
                border: 1px solid var(--accent-dim);
                background: linear-gradient(180deg, rgba(227,25,55,0.08) 0%, rgba(227,25,55,0.02) 100%);
            }
            .focus-banner.portfolio {
                border-color: var(--border-strong);
                background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%);
            }
            .focus-banner .pill {
                font-size: 0.66rem; text-transform: uppercase;
                letter-spacing: 0.16em; font-weight: 700;
                color: #FFFFFF; background: var(--accent);
                padding: 4px 10px; border-radius: 2px;
            }
            .focus-banner.portfolio .pill { background: var(--border-strong); }
            .focus-banner .text {
                color: var(--text-primary); font-size: 0.96rem; line-height: 1.45;
            }
            .focus-banner .text b { color: var(--accent); }

            .kpi-card {
                border: 1px solid var(--border);
                border-radius: 4px;
                padding: 12px 16px;
                background: var(--bg-card);
                height: 94px;
                display: flex; flex-direction: column; justify-content: center;
            }
            .kpi-card.focus {
                border-color: var(--accent);
                background: linear-gradient(180deg, rgba(227,25,55,0.07) 0%, var(--bg-card) 100%);
            }
            .kpi-label {
                font-size: 0.66rem; text-transform: uppercase;
                letter-spacing: 0.16em; color: var(--text-secondary); margin-bottom: 6px;
                font-weight: 600;
            }
            .kpi-value { font-size: 1.05rem; font-weight: 600; color: var(--text-primary); line-height: 1.3; }
            .kpi-card.focus .kpi-value { color: var(--accent); }

            .affected-card {
                border: 1px solid var(--border);
                border-radius: 4px;
                padding: 16px 18px;
                background: var(--bg-card);
                height: 420px;
                overflow: hidden;
            }
            .affected-card h4 { margin: 0 0 12px 0; font-size: 0.95rem; color: var(--text-primary); font-weight: 600; }
            .affected-card .stat-row {
                display: flex; justify-content: space-between;
                padding: 8px 0; border-bottom: 1px solid var(--border);
                color: var(--text-primary); font-size: 0.86rem;
            }
            .affected-card .stat-row:last-child { border-bottom: none; }
            .affected-card .stat-row .v { font-weight: 700; color: var(--accent); }
            .affected-card ul { margin: 10px 0 0 0; padding-left: 18px; color: var(--text-primary); font-size: 0.86rem; }
            .affected-card ul li { margin-bottom: 5px; color: var(--text-primary); }
            .affected-card .muted { color: var(--text-secondary); font-size: 0.8rem; margin-top: 6px; }

            .qa-card {
                border: 1px solid var(--border);
                border-radius: 4px;
                padding: 14px 16px;
                background: var(--bg-card);
                margin-bottom: 10px;
            }
            .qa-card h5 {
                margin: 0 0 8px 0;
                font-size: 0.7rem;
                font-weight: 600;
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.16em;
            }
            .qa-card .big {
                font-size: 1.35rem; font-weight: 700; color: var(--text-primary);
            }
            .qa-card .big.bad { color: var(--accent); }
            .qa-card .big.ok { color: var(--ok); }
            .qa-card .sub { color: var(--text-secondary); font-size: 0.82rem; margin-top: 4px; }

            [data-testid="stSidebar"] {
                background-color: var(--bg-card) !important;
                border-right: 1px solid var(--border);
            }
            [data-testid="stSidebar"] * { color: var(--text-primary) !important; }
            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] [data-baseweb="input"] input {
                background-color: var(--bg-elev) !important;
                color: var(--text-primary) !important;
                border: 1px solid var(--border-strong) !important;
                border-radius: 4px !important;
            }
            [data-testid="stSidebar"] [data-baseweb="tag"] {
                background-color: var(--accent-dim) !important;
            }
            [data-testid="stSidebar"] button {
                background-color: var(--accent) !important;
                color: #FFFFFF !important;
                border: none !important;
                border-radius: 3px !important;
                font-weight: 600 !important;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                font-size: 0.78rem !important;
            }
            [data-testid="stSidebar"] button:hover { background-color: #C01530 !important; }

            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"],
            header[data-testid="stHeader"],
            #MainMenu,
            footer { display: none !important; }

            /* Slider track */
            .stSlider [data-baseweb="slider"] div[role="slider"] {
                background-color: var(--accent) !important;
                border-color: var(--accent) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _load_cleaned_data(cleaned_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "ranking": _read_csv_if_exists(cleaned_dir / "problem_area_ranking.csv"),
        "risk_contrib": _read_csv_if_exists(cleaned_dir / "problem_score_contributions_by_site.csv"),
        "events": _read_csv_if_exists(cleaned_dir / "deployment_event_risk_by_site.csv"),
        "pain": _read_csv_if_exists(cleaned_dir / "pain_points_summary.csv"),
        "adoption": _read_csv_if_exists(cleaned_dir / "adoption_operational_metrics.csv"),
        "finance": _read_csv_if_exists(cleaned_dir / "financial_variance_by_site_category.csv"),
        "missing": _read_csv_if_exists(cleaned_dir / "missing_input_risk_by_sheet.csv"),
        "duration": _read_csv_if_exists(cleaned_dir / "deployment_duration_by_site.csv"),
        "themes": _read_csv_if_exists(cleaned_dir / "pain_themes_by_site.csv"),
        "estimate_q": _read_csv_if_exists(cleaned_dir / "austin_estimate_quality_issues.csv"),
    }


def _ensure_data_ready(cleaned_dir: Path) -> dict[str, pd.DataFrame]:
    data = _load_cleaned_data(cleaned_dir)
    required = ["ranking", "risk_contrib", "events", "pain", "adoption", "finance"]
    if any(data[k].empty for k in required):
        with st.spinner("Preparing cleaned diagnostics from source workbooks..."):
            run_inspection_analysis()
        data = _load_cleaned_data(cleaned_dir)
    return data


def render_chart(
    fig: go.Figure,
    *,
    title: str = "",
    height: int = 420,
    margin: dict | None = None,
    show_legend: bool = False,
    selectable: bool = False,
    key: str | None = None,
) -> Any:
    """Single chart entry point.

    When ``selectable`` + ``key`` are provided, the chart emits a point-selection
    event on click and the whole script reruns with the event object returned.
    """
    default_margin = {"l": 58, "r": 40, "t": 48 if title else 20, "b": 52}
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_BG_CARD,
        plot_bgcolor=_BG_CARD,
        autosize=False,
        height=height,
        margin=margin or default_margin,
        title=(
            {"text": title, "x": 0.02, "xanchor": "left",
             "font": {"size": 14, "color": _TEXT_PRIMARY, "family": "Inter, sans-serif"}}
            if title else None
        ),
        font={"color": _TEXT_PRIMARY, "size": 12, "family": "Inter, sans-serif"},
        showlegend=show_legend,
        dragmode=False,
        hoverlabel=dict(bgcolor=_BG_CARD, bordercolor=_FOCUS_COLOR,
                        font_size=12, font_family="Inter, sans-serif",
                        font_color=_TEXT_PRIMARY),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#1F1F1F", zeroline=False, linecolor=_BORDER,
        title_font={"size": 11, "color": _TEXT_SECONDARY},
        tickfont={"size": 10, "color": _TEXT_SECONDARY},
        automargin=True, fixedrange=True,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#1F1F1F", zeroline=False, linecolor=_BORDER,
        title_font={"size": 11, "color": _TEXT_SECONDARY},
        tickfont={"size": 10, "color": _TEXT_SECONDARY},
        automargin=True, fixedrange=True,
    )
    if selectable and key:
        return st.plotly_chart(
            fig,
            use_container_width=True,
            config=_PLOTLY_CONFIG,
            on_select="rerun",
            selection_mode="points",
            key=key,
        )
    st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG)
    return None


def _event_points(event: Any) -> list:
    """Defensive accessor for Plotly selection points across Streamlit versions."""
    if event is None:
        return []
    try:
        sel = event["selection"] if isinstance(event, dict) else event.selection  # type: ignore[attr-defined]
    except (KeyError, AttributeError):
        return []
    if sel is None:
        return []
    try:
        pts = sel["points"] if isinstance(sel, dict) else sel.points  # type: ignore[attr-defined]
    except (KeyError, AttributeError):
        return []
    return list(pts or [])


def _click_site_from_event(event: Any, *, source: Literal["scatter", "ranking"]) -> str | None:
    """Extract a site name from a Streamlit Plotly selection event."""
    pts = _event_points(event)
    if not pts:
        return None
    pt = pts[0]
    pt_d = pt if isinstance(pt, dict) else dict(pt)
    if source == "scatter":
        cd = pt_d.get("customdata")
        if cd and len(cd) > 0:
            return str(cd[0])
        return None
    y = pt_d.get("y")
    return str(y) if y is not None else None


def _build_delay_cost_scatter(events: pd.DataFrame, focus_site: str) -> go.Figure:
    """Delay vs disruption cost. Colorbar on right; focus highlighted with ring + label."""
    required = ("total_days_impact", "total_cost_impact", "delay_event_rate", "site")
    fig = go.Figure()
    if events.empty or not all(c in events.columns for c in required):
        return fig

    ev = events.loc[:, list(required)].copy()
    ev["_x"] = pd.to_numeric(ev["total_days_impact"], errors="coerce")
    ev["_y"] = pd.to_numeric(ev["total_cost_impact"], errors="coerce")
    ev["_rate"] = pd.to_numeric(ev["delay_event_rate"], errors="coerce").fillna(0.0)
    ev["_site"] = ev["site"].astype(str)
    ev = ev.dropna(subset=["_x", "_y"])
    if ev.empty:
        return fig

    # Focus ring drawn FIRST so the clickable marker sits on top.
    if focus_site:
        f = ev[ev["_site"] == str(focus_site)]
        if not f.empty:
            fig.add_trace(
                go.Scatter(
                    x=f["_x"], y=f["_y"], mode="markers",
                    marker=dict(
                        size=36, symbol="circle-open",
                        line=dict(width=3, color=_FOCUS_COLOR),
                        color="rgba(0,0,0,0)",
                    ),
                    hoverinfo="skip", showlegend=False,
                )
            )

    customdata = np.column_stack([ev["_site"].values, ev["_rate"].values])
    fig.add_trace(
        go.Scatter(
            x=ev["_x"], y=ev["_y"], mode="markers+text",
            text=ev["_site"], textposition="top center",
            textfont=dict(color=_TEXT_SECONDARY, size=10),
            marker=dict(
                size=18,
                color=ev["_rate"],
                cmin=0.0, cmax=max(0.01, float(ev["_rate"].max())),
                colorscale=[[0, "#2A2A2A"], [0.5, "#8E0F1F"], [1.0, _FOCUS_COLOR]],
                showscale=True,
                colorbar=dict(
                    title=dict(text="Delay-like<br>share", font=dict(size=10, color=_TEXT_SECONDARY)),
                    tickformat=".0%", len=0.75, thickness=9,
                    outlinewidth=1, outlinecolor=_BORDER,
                    tickfont=dict(color=_TEXT_SECONDARY, size=9),
                    x=1.015, xanchor="left",
                ),
                line=dict(width=1, color=_BG_CARD),
                opacity=1.0,
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Delay: %{x:.1f} days<br>"
                "Disruption cost: $%{y:,.0f}<br>"
                "Delay-like share: %{customdata[1]:.1%}"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )

    fig.update_xaxes(title="Delay impact (days)")
    fig.update_yaxes(title="Disruption cost ($)")
    return fig


def _build_sidebar_filters(data: dict[str, pd.DataFrame]) -> dict[str, list[str] | tuple[float, float]]:
    site_values: set[str] = set()
    for key in ("events", "pain", "adoption", "finance", "ranking"):
        df = data[key]
        if not df.empty and "site" in df.columns:
            site_values.update(df["site"].dropna().astype(str).unique().tolist())

    team_values: list[str] = []
    if not data["pain"].empty and "user_team" in data["pain"].columns:
        team_values = sorted(data["pain"]["user_team"].dropna().astype(str).unique().tolist())

    week_bounds = (1.0, 12.0)
    if not data["adoption"].empty and "week_num" in data["adoption"].columns:
        week_num = pd.to_numeric(data["adoption"]["week_num"], errors="coerce").dropna()
        if not week_num.empty:
            week_bounds = (float(week_num.min()), float(week_num.max()))

    st.sidebar.markdown("### Filters")
    st.sidebar.caption("Click a point / bar to deep-dive. Pick a site here to lock it.")
    selected_sites = st.sidebar.multiselect("Site", options=sorted(site_values))
    selected_teams = st.sidebar.multiselect("Team (affects pain signals only)", options=team_values)
    selected_week_range = st.sidebar.slider(
        "Deployment week (relative)",
        min_value=float(week_bounds[0]),
        max_value=float(week_bounds[1]),
        value=(float(week_bounds[0]), float(week_bounds[1])),
        step=1.0,
    )
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset focus", use_container_width=True):
        st.session_state[_SS_CLICK] = None
        st.session_state[_SS_PREV_SIDEBAR] = list(selected_sites)
        st.rerun()

    return {
        "sites": selected_sites,
        "teams": selected_teams,
        "week_range": selected_week_range,
    }


def _apply_filters(
    data: dict[str, pd.DataFrame],
    filters: dict[str, list[str] | tuple[float, float]],
) -> dict[str, pd.DataFrame]:
    sites = filters["sites"]
    teams = filters["teams"]
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
        if sites and name == "risk_contrib" and "site" in result.columns:
            result = result[result["site"].astype(str).isin(sites)]
        if name == "adoption" and "week_num" in result.columns:
            result["week_num"] = pd.to_numeric(result["week_num"], errors="coerce")
            result = result[result["week_num"].between(float(week_low), float(week_high), inclusive="both")]
        filtered[name] = result
    return filtered


def _sync_click_state(sidebar_sites: list[str]) -> None:
    """Clear the click override whenever the sidebar site selection changes."""
    if _SS_CLICK not in st.session_state:
        st.session_state[_SS_CLICK] = None
    prev = st.session_state.get(_SS_PREV_SIDEBAR)
    cur = list(sidebar_sites)
    if prev is None:
        st.session_state[_SS_PREV_SIDEBAR] = cur
    elif prev != cur:
        st.session_state[_SS_CLICK] = None
        st.session_state[_SS_PREV_SIDEBAR] = cur


def _compute_focus_state(
    filtered: dict[str, pd.DataFrame],
    filters: dict[str, list[str] | tuple[float, float]],
    clicked_site: str | None,
) -> FocusState:
    """
    Priority (highest to lowest):
      1. Click override (if clicked site is present in current ranking slice)
      2. Filtered ranking contains exactly one site → auto-focus
      3. Sidebar: 1 site selected → that site
      4. Sidebar: N sites → highest-risk among them
      5. Sidebar: 0 sites → highest-risk overall (portfolio)
    """
    sites = tuple(str(s) for s in filters["sites"])
    if filtered["ranking"].empty:
        return FocusState("portfolio", sites, "", 0.0, "none")
    rk = filtered["ranking"].sort_values("problem_score", ascending=False)

    if clicked_site:
        m = rk[rk["site"].astype(str) == str(clicked_site)]
        if not m.empty:
            return FocusState(
                "single", (str(clicked_site),),
                str(clicked_site), float(m["problem_score"].iloc[0]),
                "click",
            )

    if len(rk) == 1:
        row = rk.iloc[0]
        return FocusState("single", sites, str(row["site"]), float(row["problem_score"]), "auto")

    if len(sites) == 0:
        row = rk.iloc[0]
        return FocusState("portfolio", sites, str(row["site"]), float(row["problem_score"]), "portfolio")
    if len(sites) == 1:
        s = str(sites[0])
        m = rk[rk["site"].astype(str) == s]
        sc = float(m["problem_score"].iloc[0]) if not m.empty else 0.0
        return FocusState("single", sites, s, sc, "sidebar_single")
    sub = rk[rk["site"].astype(str).isin(sites)]
    row = (sub if not sub.empty else rk).iloc[0]
    return FocusState("multi", sites, str(row["site"]), float(row["problem_score"]), "sidebar_multi")


def _main_driver(filtered: dict[str, pd.DataFrame], site: str) -> tuple[str, str]:
    if not site or filtered["risk_contrib"].empty:
        return "", "Mixed drivers"
    sub = filtered["risk_contrib"][filtered["risk_contrib"]["site"].astype(str) == site]
    if sub.empty:
        # Fall back to full (unfiltered-by-sidebar) contribution for the clicked site.
        return "", "Mixed drivers"
    by_c = sub.groupby("component")["component_score"].sum().sort_values(ascending=False)
    top = str(by_c.index[0])
    second = str(by_c.index[1]) if len(by_c) > 1 else ""
    if top == "delay_impact" or (top == "disruption_cost" and second == "delay_impact"):
        return top, "Delay-driven cost escalation"
    return top, _MAIN_DRIVER_SUMMARY.get(top, _RISK_SCORE_COMPONENT_LABELS.get(top, top))


def _most_affected_role(filtered: dict[str, pd.DataFrame], site: str) -> str:
    if not site or filtered["pain"].empty:
        return "Site lead + PMO"
    pt = filtered["pain"][filtered["pain"]["site"].astype(str) == site].copy()
    if pt.empty:
        return "Site lead + PMO"
    hp = pd.to_numeric(pt.get("high_priority_unresolved", 0), errors="coerce").fillna(0)
    ur = pd.to_numeric(pt.get("unresolved_feedback", 0), errors="coerce").fillna(0)
    pt = pt.assign(_p=hp * 2 + ur).sort_values("_p", ascending=False)
    return str(pt.iloc[0]["user_team"])


def _decision_context(
    data: dict[str, pd.DataFrame],
    filtered: dict[str, pd.DataFrame],
    focus: FocusState,
) -> dict[str, str]:
    """Build the decision block.

    When focus comes from a click, sidebar filters may have excluded the clicked
    site from filtered ``risk_contrib`` / ``events`` / ``pain``. In that case we
    fall back to the *unfiltered* data for that site so the cards actually reflect it.
    """
    site, score = focus.focus_site, focus.focus_score
    use_unfiltered = focus.source == "click" and (
        site not in set(filtered["ranking"]["site"].astype(str).unique())
        if not filtered["ranking"].empty else False
    )
    src = data if use_unfiltered else filtered

    driver_key, driver_phrase = _main_driver(src, site)
    role = _most_affected_role(src, site)
    action = (
        _ACTION_STRIP_SHORT.get(driver_key, "Steering touchpoint + single owner")
        if driver_key else "Adjust filters"
    )

    cost_val = 0.0
    delay_val = 0.0
    if site and not src["events"].empty:
        ev = src["events"][src["events"]["site"].astype(str) == site]
        if not ev.empty:
            row = ev.iloc[0]
            cost_val = float(row["total_cost_impact"])
            delay_val = float(row["total_days_impact"])

    main_issue = (
        f"${cost_val:,.0f} disruption · {delay_val:.0f} delay-days"
        if (cost_val or delay_val) else f"Composite risk {score:.2f} in this view"
    )

    if driver_key in ("disruption_cost", "delay_impact"):
        why_now = "Highest combined cost + schedule exposure in this slice"
    elif driver_key == "budget_variance":
        why_now = "Budget drift is running ahead of controls"
    elif driver_key == "adoption_friction":
        why_now = "Blocked-user rate trending above peer sites"
    elif driver_key == "unresolved_issues":
        why_now = "High-priority feedback is still open past SLA"
    elif driver_key == "reporting_completeness_penalty":
        why_now = "Reporting gaps are masking real status"
    else:
        why_now = "Top composite risk in the current filter slice"

    return {
        "site": site or "—",
        "score": f"{score:.2f}" if site else "—",
        "driver": driver_phrase,
        "role": role,
        "action": action,
        "main_issue": main_issue,
        "why_now": why_now,
    }


def _render_mode_label(focus: FocusState) -> None:
    if focus.mode == "single":
        source_tag = {
            "click": "from click",
            "sidebar_single": "from filter",
            "auto": "auto-focused",
        }.get(focus.source, "")
        st.markdown(
            f"""
            <div class="mode-label deepdive">
                <span class="pill">Site Deep Dive</span>
                &nbsp;<span class="site">{focus.focus_site}</span>
                <span style="color:#94A3B8;font-weight:500">&nbsp;·&nbsp;{source_tag}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif focus.mode == "multi":
        st.markdown(
            f"""
            <div class="mode-label deepdive">
                <span class="pill">Compare {len(focus.selected_sites)} sites</span>
                &nbsp;anchor: <span class="site">{focus.focus_site}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="mode-label">
                <span class="pill">Portfolio View</span>
                <span style="color:#94A3B8;font-weight:500">&nbsp;· click a bar or a point to deep-dive</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_focus_banner(focus: FocusState, ctx: dict[str, str]) -> None:
    site = ctx["site"]
    score = ctx["score"]
    if focus.mode == "portfolio":
        cls, pill = "focus-banner portfolio", "Portfolio view"
        text = (
            f"Showing all sites. Narrative anchor: <b>{site}</b> "
            f"(highest composite risk, {score}). Click a point/bar or pick a site to zoom in."
        )
    elif focus.mode == "single":
        cls, pill = "focus-banner", "Site diagnosis"
        text = (
            f"Locked on <b>{site}</b> — composite risk {score}. "
            f"All charts, KPIs, and the action below are specific to this site."
        )
    else:
        cls, pill = "focus-banner", f"{len(focus.selected_sites)} sites"
        text = (
            f"Comparing {len(focus.selected_sites)} sites. Anchor: <b>{site}</b> "
            f"(highest composite, {score})."
        )
    st.markdown(
        f"""
        <div class="{cls}">
            <div class="pill">{pill}</div>
            <div class="text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_decision_strip(ctx: dict[str, str]) -> None:
    cols = st.columns(4, gap="medium")
    cards = [
        ("Priority site", ctx["site"], True),
        ("Main driver", ctx["driver"], False),
        ("Most affected role", ctx["role"], False),
        ("Recommended action", ctx["action"], False),
    ]
    for col, (lbl, val, is_focus) in zip(cols, cards):
        with col:
            cls = "kpi-card focus" if is_focus else "kpi-card"
            st.markdown(
                f"""
                <div class="{cls}">
                    <div class="kpi-label">{lbl}</div>
                    <div class="kpi-value">{val}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_action_block(ctx: dict[str, str]) -> None:
    if ctx["site"] == "—":
        st.caption("No ranking in this slice — widen filters.")
        return
    who = ctx["role"] if ctx["role"] not in ("—", "No team slice in view") else "Site lead + PMO"
    st.markdown(
        f"- **Focus site:** {ctx['site']}  \n"
        f"- **Main issue:** {ctx['main_issue']}  \n"
        f"- **Why now:** {ctx['why_now']}  \n"
        f"- **Who to engage:** {who}  \n"
        f"- **Immediate move:** {ctx['action']} on {ctx['site']} this week"
    )


def _render_affected_card(
    data: dict[str, pd.DataFrame],
    filtered: dict[str, pd.DataFrame],
    focus: FocusState,
) -> None:
    site = focus.focus_site
    # Use unfiltered pain if click landed outside current sidebar scope — keeps the card site-specific.
    src_pain = (
        data["pain"]
        if focus.source == "click" and not filtered["pain"].empty and
           site not in set(filtered["pain"]["site"].astype(str).unique())
        else filtered["pain"]
    )
    header = f"Affected at <b style='color:{_FOCUS_COLOR}'>{site}</b>" if site else "Affected (portfolio)"

    if src_pain.empty or not site:
        st.markdown(
            f"""
            <div class="affected-card">
                <h4>{header}</h4>
                <div class="muted">No feedback data for current filters.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    site_pain = src_pain[src_pain["site"].astype(str) == str(site)].copy()
    if site_pain.empty:
        site_pain = src_pain.copy()
        header = "Affected (portfolio — no rows at focus)"

    total_teams = int(site_pain["user_team"].nunique())
    unresolved = int(pd.to_numeric(site_pain["unresolved_feedback"], errors="coerce").fillna(0).sum())
    missing_status = int(pd.to_numeric(site_pain["missing_status_count"], errors="coerce").fillna(0).sum())
    high_pri = int(pd.to_numeric(site_pain["high_priority_unresolved"], errors="coerce").fillna(0).sum())

    site_pain = site_pain.assign(
        _severity=(
            pd.to_numeric(site_pain["high_priority_unresolved"], errors="coerce").fillna(0) * 3
            + pd.to_numeric(site_pain["unresolved_feedback"], errors="coerce").fillna(0) * 2
            + pd.to_numeric(site_pain["missing_status_count"], errors="coerce").fillna(0)
        )
    )
    top_teams = site_pain.sort_values(["_severity", "user_team"], ascending=[False, True]).head(5)
    rows_html = "".join(
        f"<li><b>{row['user_team']}</b> — {row['feedback_type']}"
        + (
            f"  ·  <span style='color:{_FOCUS_COLOR}'>unresolved</span>"
            if int(pd.to_numeric(row.get("unresolved_feedback", 0), errors="coerce") or 0) > 0 else ""
        )
        + (
            f"  ·  <span style='color:{_TEXT_SECONDARY}'>status missing</span>"
            if int(pd.to_numeric(row.get("missing_status_count", 0), errors="coerce") or 0) > 0 else ""
        )
        + "</li>"
        for _, row in top_teams.iterrows()
    )
    if not rows_html:
        rows_html = "<li class='muted'>No teams flagged.</li>"

    st.markdown(
        f"""
        <div class="affected-card">
            <h4>{header}</h4>
            <div class="stat-row"><span>Teams raising feedback</span><span class="v">{total_teams}</span></div>
            <div class="stat-row"><span>Unresolved items</span><span class="v">{unresolved}</span></div>
            <div class="stat-row"><span>Missing status</span><span class="v">{missing_status}</span></div>
            <div class="stat-row"><span>High-priority open</span><span class="v">{high_pri}</span></div>
            <div style="margin-top:12px;font-size:0.74rem;color:{_TEXT_SECONDARY};letter-spacing:0.12em;text-transform:uppercase;font-weight:600;">Top teams (severity-ranked)</div>
            <ul>{rows_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_duration_section(duration_df: pd.DataFrame) -> None:
    if duration_df.empty:
        return
    st.markdown(
        "<div class='section-header'>Deployment Velocity · Previous Sites</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='hint'>Target: 4 weeks to Athena go-live. Shanghai/Mexico are the playbook; Berlin is the anti-pattern.</div>",
        unsafe_allow_html=True,
    )

    col_chart, col_kpi = st.columns([2.1, 1], gap="medium")
    with col_chart:
        d = duration_df.sort_values("actual_weeks", ascending=True).copy()
        colors = [_FOCUS_COLOR if w > 4 else _GOOD if w < 4 else _TEXT_SECONDARY for w in d["actual_weeks"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=d["actual_weeks"], y=d["site"], orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{w:.1f} wk" for w in d["actual_weeks"]],
            textposition="outside",
            textfont=dict(size=11, color=_TEXT_PRIMARY),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Actual: %{x:.1f} wk<br>Target: 4.0 wk<extra></extra>",
        ))
        fig.add_vline(
            x=4, line_dash="dash", line_color=_TEXT_SECONDARY,
            annotation_text="Target 4w", annotation_position="top",
            annotation_font_color=_TEXT_SECONDARY, annotation_font_size=10,
        )
        fig.update_layout(xaxis_title="Weeks to go-live", yaxis_title="")
        render_chart(
            fig, title="Weeks to Go-Live · Actual vs 4-Week Target",
            height=260, margin={"l": 86, "r": 30, "t": 42, "b": 46},
        )

    with col_kpi:
        worst = duration_df.iloc[0]
        best = duration_df.iloc[-1]
        on_target = int((duration_df["overrun_weeks"] <= 0).sum())
        total = len(duration_df)
        st.markdown(
            f"""
            <div class='qa-card'>
                <h5>Worst — Overrun Champion</h5>
                <div class='big bad'>{worst['site']} · {worst['actual_weeks']:.1f} wk</div>
                <div class='sub'>+{worst['overrun_weeks']:.1f} weeks over target ({worst['overrun_pct']:+.0f}%)</div>
            </div>
            <div class='qa-card'>
                <h5>Best — Reference Playbook</h5>
                <div class='big ok'>{best['site']} · {best['actual_weeks']:.1f} wk</div>
                <div class='sub'>{best['overrun_weeks']:+.1f} wk vs target</div>
            </div>
            <div class='qa-card'>
                <h5>On / Under Target</h5>
                <div class='big'>{on_target} of {total}</div>
                <div class='sub'>Out of {total} prior deployments</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_themes_section(themes_df: pd.DataFrame) -> None:
    if themes_df.empty:
        return
    st.markdown(
        "<div class='section-header'>User Pain · Cross-Site Themes</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='hint'>Every theme appears at ≥4 of 5 sites — these are platform-level gaps, not site-specific.</div>",
        unsafe_allow_html=True,
    )

    col_tot, col_heat = st.columns([1, 1.4], gap="medium")
    with col_tot:
        totals = (
            themes_df.drop_duplicates("theme")[["theme", "total_mentions", "high_total"]]
            .sort_values("total_mentions", ascending=True)
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=totals["total_mentions"], y=totals["theme"], orientation="h",
            marker=dict(color=_FOCUS_COLOR, line=dict(width=0)),
            text=[f"{int(m)} ({int(h)} high)" for m, h in zip(totals["total_mentions"], totals["high_total"])],
            textposition="outside",
            textfont=dict(size=10, color=_TEXT_PRIMARY),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Mentions: %{x}<extra></extra>",
        ))
        fig.update_layout(xaxis_title="Feedback mentions", yaxis_title="")
        render_chart(
            fig, title="Theme frequency (38 feedback items, 5 sites)",
            height=380, margin={"l": 220, "r": 30, "t": 42, "b": 46},
        )

    with col_heat:
        pivot = themes_df.pivot_table(
            index="theme", columns="site", values="mentions", aggfunc="sum", fill_value=0
        )
        theme_order = (
            themes_df.drop_duplicates("theme")[["theme", "total_mentions"]]
            .sort_values("total_mentions", ascending=True)
        )["theme"].tolist()
        pivot = pivot.reindex(theme_order)
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=[[0, _BG_CARD], [0.3, "#3A0A12"], [0.7, "#8E0F1F"], [1.0, _FOCUS_COLOR]],
            colorbar=dict(
                title=dict(text="Mentions", font=dict(size=10, color=_TEXT_SECONDARY)),
                tickfont=dict(color=_TEXT_SECONDARY, size=9),
                thickness=9, len=0.75, outlinewidth=1, outlinecolor=_BORDER,
            ),
            text=pivot.values, texttemplate="%{text}",
            textfont=dict(color=_TEXT_PRIMARY, size=11),
            hovertemplate="<b>%{y}</b> · %{x}<br>%{z} mentions<extra></extra>",
        ))
        fig.update_layout(xaxis_title="", yaxis_title="")
        render_chart(
            fig, title="Theme × site — where pain concentrates",
            height=380, margin={"l": 220, "r": 30, "t": 42, "b": 46},
        )


def _render_estimate_section(estimate_df: pd.DataFrame) -> None:
    if estimate_df.empty:
        return
    st.markdown(
        "<div class='section-header'>Austin · Day-1 Estimate Data Quality</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='hint'>The Athena project breakout comes from this Estimate. Fix these before Day 1 or the import fails.</div>",
        unsafe_allow_html=True,
    )

    total_defects = int(estimate_df["rows_affected"].sum())
    defect_categories = len(estimate_df)
    st.markdown(
        f"""
        <div class='qa-card' style='margin-bottom:12px'>
            <h5>Defects Found Before Import</h5>
            <div class='big bad'>{total_defects} cells · {defect_categories} defect types</div>
            <div class='sub'>Across 36 scope rows in the Austin Building 1 estimate</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows_html = "".join(
        f"""
        <div class='stat-row' style='padding:10px 0;display:grid;grid-template-columns:1.2fr 2fr 0.5fr 2.2fr;gap:10px;'>
            <div><b style='color:{_FOCUS_COLOR}'>{row['field']}</b></div>
            <div>{row['defect']}</div>
            <div style='text-align:right;font-weight:600;'>{row['rows_affected']}</div>
            <div style='color:{_TEXT_SECONDARY};font-size:0.84rem;'>{row['impact']}</div>
        </div>
        """
        for _, row in estimate_df.iterrows()
    )
    st.markdown(
        f"""
        <div class='affected-card' style='height:auto;'>
            <div class='stat-row' style='padding:6px 0;display:grid;grid-template-columns:1.2fr 2fr 0.5fr 2.2fr;gap:10px;color:{_TEXT_SECONDARY};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.14em;font-weight:600;'>
                <div>Field</div><div>Defect</div><div style='text-align:right;'>Rows</div><div>Import Impact</div>
            </div>
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_styles()
    st.markdown(
        """
        <div class='brand-row'>
            <div class='brand-left'>
                <div class='brand-mark'>TESLA</div>
                <div class='brand-pipe'></div>
                <div class='brand-product'>Athena FDE Console <span class='muted'>· Deployment Diagnostics</span></div>
            </div>
            <div class='brand-right'>Gigafactory · Austin · Building 1</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    root = get_project_root()
    cleaned_dir = root / "outputs" / "cleaned"
    data = _ensure_data_ready(cleaned_dir)

    filters = _build_sidebar_filters(data)
    _sync_click_state(filters["sites"])  # clear click override when sidebar changes

    filtered = _apply_filters(data, filters)

    # Reserve the top slots; they are filled AFTER the clickable charts so any click
    # this run is already reflected in the banner / strip / mode label.
    mode_slot = st.empty()
    banner_slot = st.empty()
    strip_slot = st.empty()
    velocity_slot = st.empty()

    st.markdown(
        "<div class='section-header'>Where it's worst · why it's risky</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='hint'>Click any bar or scatter point to deep-dive that site.</div>",
        unsafe_allow_html=True,
    )
    col_left, col_right = st.columns(2, gap="medium")

    # We have to compute a provisional focus_site for highlighting BEFORE we know
    # whether a click just happened this run. Using the current click state is fine:
    # if the user clicks a new site, the script reruns with the updated state on
    # the NEXT pass — and since the charts are re-rendered on every rerun, the
    # highlight updates immediately for the viewer.
    current_click = st.session_state.get(_SS_CLICK)
    provisional_focus = _compute_focus_state(filtered, filters, current_click)
    focus_site_pre = provisional_focus.focus_site

    ranking_event = None
    scatter_event = None

    with col_right:
        if not filtered["ranking"].empty:
            ranking_plot = (
                filtered["ranking"].sort_values("problem_score", ascending=False).head(10)
            )
            bar_colors = [
                _FOCUS_COLOR if str(s) == str(focus_site_pre) else _MUTED_COLOR
                for s in ranking_plot["site"]
            ]
            text_labels = [f"{v:.2f}" for v in ranking_plot["problem_score"]]
            fig_rank = go.Figure(
                go.Bar(
                    x=ranking_plot["problem_score"],
                    y=ranking_plot["site"],
                    orientation="h",
                    marker=dict(color=bar_colors, line=dict(width=0)),
                    text=text_labels,
                    textposition="outside",
                    textfont=dict(size=11, color=_TEXT_PRIMARY),
                    cliponaxis=False,
                    hovertemplate="<b>%{y}</b><br>Composite risk: %{x:.2f}<br><i>click to deep-dive</i><extra></extra>",
                )
            )
            fig_rank.update_layout(
                xaxis_title="Composite risk score",
                yaxis_title="",
                yaxis=dict(autorange="reversed"),
            )
            ranking_event = render_chart(
                fig_rank,
                title="Where to act first",
                height=420,
                margin={"l": 92, "r": 44, "t": 48, "b": 46},
                selectable=True,
                key="ranking_chart",
            )
        else:
            st.info("No ranking data for current filters.")

    with col_left:
        if not filtered["events"].empty:
            fig_scatter = _build_delay_cost_scatter(filtered["events"], focus_site_pre)
            scatter_event = render_chart(
                fig_scatter,
                title="Why it's risky: delay vs. disruption cost",
                height=420,
                margin={"l": 62, "r": 110, "t": 48, "b": 52},
                selectable=True,
                key="scatter_chart",
            )
        else:
            st.info("No deployment event data for current filters.")

    # --- Resolve click events (if any) and recompute focus before rendering the rest. ---
    new_click: str | None = None
    from_scatter = _click_site_from_event(scatter_event, source="scatter")
    from_ranking = _click_site_from_event(ranking_event, source="ranking")
    if from_scatter:
        new_click = from_scatter
    elif from_ranking:
        new_click = from_ranking

    if new_click and new_click != current_click:
        st.session_state[_SS_CLICK] = new_click
        st.rerun()

    focus = provisional_focus  # no new click this pass
    ctx = _decision_context(data, filtered, focus)

    # Fill the top slots with the now-resolved focus.
    with mode_slot.container():
        _render_mode_label(focus)
    with banner_slot.container():
        _render_focus_banner(focus, ctx)
    with strip_slot.container():
        _render_decision_strip(ctx)
    with velocity_slot.container():
        _render_duration_section(filtered.get("duration", pd.DataFrame()))

    # ---- Who is affected ----
    st.markdown("<div class='section-header'>Who is affected?</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1.2], gap="medium")

    with col_a:
        _render_affected_card(data, filtered, focus)

    with col_b:
        if not filtered["adoption"].empty:
            adoption_plot = filtered["adoption"].dropna(subset=["week_num"]).copy()
            if not adoption_plot.empty:
                sites_in_plot = adoption_plot["site"].astype(str).unique().tolist()
                color_map = {
                    s: (_FOCUS_COLOR if s == str(focus.focus_site) else _MUTED_COLOR)
                    for s in sites_in_plot
                }
                fig_adoption = px.line(
                    adoption_plot,
                    x="week_num",
                    y="blocked_rate",
                    color="site",
                    markers=True,
                    labels={"week_num": "Deployment week", "blocked_rate": "Blocked user rate"},
                    color_discrete_map=color_map,
                )
                for tr in fig_adoption.data:
                    name = str(getattr(tr, "name", "") or "")
                    if name == str(focus.focus_site):
                        tr.update(line=dict(width=4), opacity=1.0, marker=dict(size=8))
                    else:
                        tr.update(line=dict(width=1.5), opacity=0.35, marker=dict(size=4))
                fig_adoption.update_yaxes(tickformat=".0%")

                if focus.focus_site:
                    f_df = adoption_plot[adoption_plot["site"].astype(str) == str(focus.focus_site)].sort_values("week_num")
                    if not f_df.empty:
                        fig_adoption.add_annotation(
                            x=float(f_df["week_num"].iloc[-1]),
                            y=float(f_df["blocked_rate"].iloc[-1]),
                            text=f"<b>{focus.focus_site}</b>",
                            showarrow=False, xshift=10, yshift=10,
                            font=dict(size=12, color=_FOCUS_COLOR),
                            bgcolor=_BG_CARD,
                            bordercolor=_FOCUS_COLOR, borderwidth=1, borderpad=4,
                        )
                render_chart(
                    fig_adoption,
                    title="Adoption trend: blocked-user rate by week",
                    height=420,
                    margin={"l": 64, "r": 44, "t": 48, "b": 52},
                )
            else:
                st.info("No week-level adoption rows for current filters.")
        else:
            st.info("No adoption data for current filters.")

    # ---- Pain themes cross-site ---- (always aggregate across all 5 sites, ignore sidebar filter)
    _render_themes_section(data.get("themes", pd.DataFrame()))

    # ---- Austin Day-1 data quality ----
    _render_estimate_section(data.get("estimate_q", pd.DataFrame()))

    # ---- What to do next ----
    st.markdown("<div class='section-header'>What to do next</div>", unsafe_allow_html=True)
    _render_action_block(ctx)


if __name__ == "__main__":
    main()
