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

_FOCUS_COLOR = "#1D4ED8"
_MUTED_COLOR = "#CBD5E1"

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
    """Light presentation theme. Nothing here controls chart height — Plotly owns that."""
    st.markdown(
        """
        <style>
            :root {
                --bg-main: #F7F9FB;
                --text-primary: #0F172A;
                --text-secondary: #334155;
                --border-soft: #D9E2EC;
                --focus: #1D4ED8;
            }
            * { font-family: Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
            .stApp { background-color: var(--bg-main); color: var(--text-primary); }
            .stApp, [data-testid="stAppViewContainer"] { color-scheme: light; }
            .stApp [data-testid="stMarkdownContainer"] p,
            .stApp [data-testid="stMarkdownContainer"] li { color: #0F172A; }
            .block-container { padding-top: 0.5rem; padding-bottom: 0.75rem; max-width: 1450px; }
            h1, h2, h3 { color: var(--text-primary); letter-spacing: 0.2px; }
            .main-title {
                text-align: center; font-size: 1.65rem; font-weight: 750;
                color: #0B1733; margin-bottom: 0.05rem;
            }
            .app-subtitle {
                color: var(--text-secondary); margin: -2px 0 6px 0;
                font-size: 0.88rem; text-align: center;
            }
            .mode-label {
                text-align: center;
                margin: 0 0 6px 0;
                font-size: 0.78rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                font-weight: 700;
            }
            .mode-label .pill {
                display: inline-block;
                padding: 3px 12px;
                border-radius: 999px;
                color: #FFFFFF;
                background: #64748B;
            }
            .mode-label.deepdive .pill { background: var(--focus); }
            .mode-label .site { color: var(--focus); font-weight: 700; }
            .section-header {
                font-size: 1rem; font-weight: 650; color: #13233F;
                padding: 0.25rem 0.2rem;
                border-bottom: 1px solid var(--border-soft);
                margin: 0.5rem 0 0.35rem 0;
            }
            .hint {
                color: #64748B; font-size: 0.78rem; margin: -2px 0 6px 2px;
            }

            .focus-banner {
                display: flex; align-items: center; gap: 14px;
                border-radius: 12px; padding: 10px 16px;
                margin: 0.3rem 0 0.55rem 0;
                border: 1px solid #BFDBFE;
                background: linear-gradient(180deg, #EFF6FF 0%, #FFFFFF 100%);
            }
            .focus-banner.portfolio {
                border-color: #E2E8F0;
                background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
            }
            .focus-banner .pill {
                font-size: 0.7rem; text-transform: uppercase;
                letter-spacing: 0.08em; font-weight: 700;
                color: #FFFFFF; background: var(--focus);
                padding: 4px 10px; border-radius: 999px;
            }
            .focus-banner.portfolio .pill { background: #64748B; }
            .focus-banner .text {
                color: #0B1733; font-size: 0.98rem; line-height: 1.35;
            }
            .focus-banner .text b { color: var(--focus); }

            .kpi-card {
                border: 1px solid var(--border-soft);
                border-radius: 10px;
                padding: 10px 14px;
                background: #FFFFFF;
                height: 88px;
                display: flex; flex-direction: column; justify-content: center;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
            }
            .kpi-card.focus {
                border-color: var(--focus);
                box-shadow: 0 1px 3px rgba(29, 78, 216, 0.15);
            }
            .kpi-label {
                font-size: 0.7rem; text-transform: uppercase;
                letter-spacing: 0.06em; color: #64748B; margin-bottom: 4px;
            }
            .kpi-value { font-size: 1.0rem; font-weight: 650; color: #0F172A; line-height: 1.25; }
            .kpi-card.focus .kpi-value { color: var(--focus); }

            .affected-card {
                border: 1px solid var(--border-soft);
                border-radius: 10px;
                padding: 14px 16px;
                background: #FFFFFF;
                height: 420px;
                overflow: hidden;
            }
            .affected-card h4 { margin: 0 0 10px 0; font-size: 0.95rem; color: #0F172A; }
            .affected-card .stat-row {
                display: flex; justify-content: space-between;
                padding: 6px 0; border-bottom: 1px dashed #E5E7EB;
                color: #0F172A; font-size: 0.88rem;
            }
            .affected-card .stat-row:last-child { border-bottom: none; }
            .affected-card .stat-row .v { font-weight: 700; color: var(--focus); }
            .affected-card ul { margin: 8px 0 0 0; padding-left: 18px; color: #0F172A; font-size: 0.88rem; }
            .affected-card ul li { margin-bottom: 3px; }
            .affected-card .muted { color: #64748B; font-size: 0.8rem; margin-top: 6px; }

            [data-testid="stSidebar"] {
                background-color: #FFFFFF !important;
                border-right: 1px solid var(--border-soft);
            }
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #1E293B !important; }
            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] [data-baseweb="input"] input {
                background-color: #FFFFFF !important;
                color: #0F172A !important;
                border: 1px solid #CBD5E1 !important;
                border-radius: 8px !important;
            }
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            [data-testid="stStatusWidget"],
            header[data-testid="stHeader"],
            #MainMenu,
            footer { display: none !important; }
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
    }


def _ensure_data_ready(cleaned_dir: Path) -> dict[str, pd.DataFrame]:
    data = _load_cleaned_data(cleaned_dir)
    if any(df.empty for df in data.values()):
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
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        autosize=False,
        height=height,
        margin=margin or default_margin,
        title=(
            {"text": title, "x": 0.5, "xanchor": "center",
             "font": {"size": 15, "color": "#0F172A"}}
            if title else None
        ),
        font={"color": "#0F172A", "size": 13},
        showlegend=show_legend,
        dragmode=False,
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12, font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#E8EDF3", zeroline=False, linecolor="#94A3B8",
        title_font={"size": 12, "color": "#0F172A"}, tickfont={"size": 11, "color": "#334155"},
        automargin=True, fixedrange=True,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#E8EDF3", zeroline=False, linecolor="#94A3B8",
        title_font={"size": 12, "color": "#0F172A"}, tickfont={"size": 11, "color": "#334155"},
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

    # Focus ring is drawn FIRST so the clickable marker sits on top (click + hover both work).
    if focus_site:
        f = ev[ev["_site"] == str(focus_site)]
        if not f.empty:
            fig.add_trace(
                go.Scatter(
                    x=f["_x"], y=f["_y"], mode="markers",
                    marker=dict(
                        size=34, symbol="circle-open",
                        line=dict(width=3, color=_FOCUS_COLOR),
                        color="rgba(0,0,0,0)",
                    ),
                    hoverinfo="skip", showlegend=False,
                )
            )

    customdata = np.column_stack([ev["_site"].values, ev["_rate"].values])
    fig.add_trace(
        go.Scatter(
            x=ev["_x"], y=ev["_y"], mode="markers",
            marker=dict(
                size=16,
                color=ev["_rate"],
                cmin=0.0, cmax=max(0.01, float(ev["_rate"].max())),
                colorscale="YlOrRd", showscale=True,
                colorbar=dict(
                    title=dict(text="Delay-like<br>share", font=dict(size=11, color="#111827")),
                    tickformat=".0%", len=0.75, thickness=10,
                    outlinewidth=1, outlinecolor="#CBD5E1",
                    x=1.015, xanchor="left",
                ),
                line=dict(width=0.5, color="#FFFFFF"),
                opacity=0.95,
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

    if focus_site:
        f = ev[ev["_site"] == str(focus_site)]
        if not f.empty:
            fx = float(f["_x"].iloc[0])
            fy = float(f["_y"].iloc[0])
            fig.add_annotation(
                x=fx, y=fy, text=f"<b>{focus_site}</b>",
                showarrow=False, yshift=26,
                font=dict(size=12, color=_FOCUS_COLOR),
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor=_FOCUS_COLOR, borderwidth=1, borderpad=3,
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
            "  ·  <span style='color:#B91C1C'>unresolved</span>"
            if int(pd.to_numeric(row.get("unresolved_feedback", 0), errors="coerce") or 0) > 0 else ""
        )
        + (
            "  ·  <span style='color:#64748B'>status missing</span>"
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
            <div style="margin-top:10px;font-size:0.82rem;color:#64748B;">Top teams (severity-ranked)</div>
            <ul>{rows_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    _inject_styles()
    st.markdown(
        "<div class='main-title'>Tesla FDE Deployment Monitoring Dashboard</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='app-subtitle'>The problem → where it's worst → why it's risky → who's affected → what to do.</div>",
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
                    textfont=dict(size=11, color="#0F172A"),
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
                            showarrow=False, xshift=8, yshift=10,
                            font=dict(size=12, color=_FOCUS_COLOR),
                            bgcolor="rgba(255,255,255,0.9)",
                            bordercolor=_FOCUS_COLOR, borderwidth=1, borderpad=3,
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

    # ---- What to do next ----
    st.markdown("<div class='section-header'>What to do next</div>", unsafe_allow_html=True)
    _render_action_block(ctx)


if __name__ == "__main__":
    main()
