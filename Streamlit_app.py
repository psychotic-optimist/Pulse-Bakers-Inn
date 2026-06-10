"""
streamlit_app.py — Bakery Dispatch Control Tower
Main application entry-point.
"""

from __future__ import annotations

import io
import logging
import math
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import dispatch_auth as auth
import calculations
import database as db
import depot_database as ddb
from depot_importer import parse_depot_excel
from config import (
    ALL_STATUSES,
    AUTOREFRESH_MS,
    BOARD_COLUMNS,
    DISPLAY_TIMEZONE,
    MANUAL_OVERRIDE_STATUSES,
    STATUS_DISPATCHED,
    STATUS_IN_QUEUE,
    STATUS_LOADED,
    STATUS_LOADING,
    STATUS_AWAITING,
    TV_DISPLAY_PARAM,
)
from importer import parse_all_sheets

# Baker's Inn logo (base64 embedded)
_LOGO_B64 = "data:image/jpeg;base64,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"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ===========================================================================
# Page config
# ===========================================================================

def _is_tv_mode() -> bool:
    params = st.query_params
    return params.get(TV_DISPLAY_PARAM, "").lower() in ("true", "1", "yes")


st.set_page_config(
    page_title="Baker's Inn | Dispatch Control Tower",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed" if _is_tv_mode() else "expanded",
)

# ===========================================================================
# Custom CSS
# ===========================================================================

def _inject_css(tv_mode: bool) -> None:
    # Baker's Inn brand palette:  Navy #1B2D6B  |  Gold #C9A84C  |  Warm bg #FBF5E6
    font_scale = "1.4rem" if tv_mode else "0.95rem"
    table_font = "1.1rem" if tv_mode else "0.85rem"
    st.markdown(
        f"""
        <style>
        /* ── Base ── */
        html, body, [class*="css"] {{ font-size: {font_scale}; }}

        /* ── Streamlit primary buttons → navy ── */
        div.stButton > button[kind="primary"] {{
            background-color: #1B2D6B !important;
            color: #ffffff !important;
            border: none;
        }}
        div.stButton > button[kind="primary"]:hover {{
            background-color: #152356 !important;
        }}

        /* ── Sidebar brand block ── */
        .bi-sidebar-brand {{
            background: linear-gradient(160deg, #1B2D6B 0%, #152356 100%);
            border-radius: 10px;
            padding: 1rem 0.75rem 0.75rem 0.75rem;
            text-align: center;
            margin-bottom: 0.75rem;
        }}
        .bi-sidebar-brand img {{
            width: 110px;
            height: auto;
            display: block;
            margin: 0 auto 6px auto;
        }}
        .bi-sidebar-sub {{
            color: #C9A84C;
            font-size: 0.72em;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin: 0;
        }}

        /* ── Page header banner ── */
        .bi-page-header {{
            background: linear-gradient(135deg, #1B2D6B 0%, #2a4298 100%);
            border-radius: 10px;
            padding: 0.85rem 1.5rem;
            margin-bottom: 1.1rem;
            display: flex;
            align-items: center;
            gap: 1.1rem;
        }}
        .bi-page-header img {{
            height: 54px;
            width: auto;
        }}
        .bi-page-header-title {{
            color: #ffffff;
            font-size: 1.4em;
            font-weight: 800;
            margin: 0;
            line-height: 1.2;
        }}
        .bi-page-header-sub {{
            color: #C9A84C;
            font-size: 0.78em;
            margin: 3px 0 0 0;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        /* ── Status badges ── */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.82em;
            letter-spacing: 0.3px;
        }}
        .badge-queue    {{ background: #fee2e2; color: #991b1b; }}
        .badge-loading  {{ background: #dcfce7; color: #166534; }}
        .badge-loaded   {{ background: #dbeafe; color: #1e40af; }}
        .badge-await    {{ background: #fef9c3; color: #713f12; }}
        .badge-dispatch {{ background: #f3f4f6; color: #111827; }}

        /* ── KPI cards ── */
        .kpi-card {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-top: 3px solid #C9A84C;
            border-radius: 10px;
            padding: 1rem 1.25rem;
            text-align: center;
            box-shadow: 0 2px 6px rgba(27,45,107,.07);
        }}
        .kpi-label {{
            font-size: 0.74em;
            color: #1B2D6B;
            font-weight: 700;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }}
        .kpi-value {{ font-size: 1.8em; font-weight: 700; color: #1B2D6B; }}
        .kpi-delta {{ font-size: 0.75em; color: #6b7280; }}

        /* ── Airport board table ── */
        .board-table {{ font-size: {table_font}; width: 100%; border-collapse: collapse; }}
        .board-table th {{
            background: #1B2D6B;
            color: #C9A84C;
            padding: 9px 12px;
            text-align: left;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            font-size: 0.88em;
        }}
        .board-table td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
        .board-table tr:hover td {{ background: #FBF5E6; }}

        /* ── Progress bar ── */
        .prog-bg  {{ background: #e5e7eb; border-radius: 6px; height: 10px; width: 100%; }}
        .prog-fill {{ border-radius: 6px; height: 10px; }}

        /* ── Section divider ── */
        .bi-divider {{
            border: none;
            border-top: 2px solid #C9A84C;
            margin: 1.5rem 0 1rem 0;
            opacity: 0.4;
        }}

        /* ── Pulse copyright footer ── */
        .pulse-footer {{
            margin-top: 2.5rem;
            padding: 0.8rem 0;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            font-size: 0.73em;
            color: #9ca3af;
        }}
        .pulse-logo-inline {{
            display: inline-block;
            background: linear-gradient(135deg, #1B7CED, #0D4FA8);
            color: white;
            font-weight: 900;
            font-size: 11px;
            width: 17px; height: 17px; line-height: 17px;
            border-radius: 3px;
            text-align: center;
            margin-right: 4px;
            vertical-align: middle;
        }}
        .pulse-footer a {{ color: #1B7CED; text-decoration: none; font-weight: 600; }}

        /* ── Mobile ── */
        @media (max-width: 768px) {{
            .kpi-value {{ font-size: 1.4em; }}
            .board-table {{ font-size: 0.78rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_pulse_footer() -> None:
    from datetime import date as _d
    yr = _d.today().year
    st.markdown(
        f"""<div class='pulse-footer'>
            <span class='pulse-logo-inline'>P</span>
            Designed &amp; developed by <a href='#'>Pulse Ltd</a>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            &copy; {yr} Baker's Inn &nbsp;&mdash;&nbsp; All rights reserved.
        </div>""",
        unsafe_allow_html=True,
    )


# ===========================================================================
# Helper renderers
# ===========================================================================

def _status_badge(status: str) -> str:
    cls_map = {
        STATUS_IN_QUEUE: "badge-queue",
        STATUS_LOADING: "badge-loading",
        STATUS_LOADED: "badge-loaded",
        STATUS_AWAITING: "badge-await",
        STATUS_DISPATCHED: "badge-dispatch",
    }
    cls = cls_map.get(status, "badge-queue")
    return f"<span class='badge {cls}'>{status}</span>"


def _progress_bar_html(pct: float) -> str:
    color = "#22c55e" if pct >= 100 else ("#3b82f6" if pct >= 50 else "#f59e0b")
    return (
        f"<div class='prog-bg'>"
        f"<div class='prog-fill' style='width:{min(pct,100):.0f}%;background:{color};'></div>"
        f"</div><small>{pct:.0f}%</small>"
    )


def _kpi_card(label: str, value: str, delta: Optional[str] = None) -> str:
    delta_html = f"<div style='font-size:0.75em;color:#6b7280;'>{delta}</div>" if delta else ""
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"{delta_html}"
        f"</div>"
    )


# ===========================================================================
# KPI Cards section
# ===========================================================================

def render_kpi_cards(orders: list[dict], settings: dict) -> None:
    buffer = settings.get("current_bin_level", 0)
    rate = settings.get("hourly_production_rate", 5000)
    total_demand = calculations.kpi_total_demand(orders)
    total_remaining = calculations.kpi_total_remaining(orders)
    overall_pct = calculations.kpi_overall_progress(orders)
    finish_dt = calculations.kpi_estimated_finish(orders, rate, buffer)
    finish_str = calculations.format_etc(finish_dt) if finish_dt else "Done"

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Opening Stock", f"{buffer:,}", "loaves in bin"),
        (c2, "Hourly Rate", f"{rate:,}", "loaves/hour"),
        (c3, "Total Demand", f"{total_demand:,}", "loaves today"),
        (c4, "Remaining", f"{total_remaining:,}", f"{overall_pct:.0f}% loaded"),
        (c5, "Est. Finish", finish_str, "all routes done"),
    ]
    for col, label, value, delta in cards:
        with col:
            st.markdown(_kpi_card(label, value, delta), unsafe_allow_html=True)


# ===========================================================================
# Airport board — one tab
# ===========================================================================

def render_board_tab(
    orders: list[dict],
    hourly_rate: int,
    tv_mode: bool,
    tab_label: str,
) -> None:
    if not orders:
        st.info(f"No {tab_label} orders for today.")
        return

    augmented = calculations.augment_orders(orders, hourly_rate)

    rows_html = ""
    for o in augmented:
        rows_html += (
            f"<tr>"
            f"<td><b>{o.get('route_name','')}</b></td>"
            f"<td>{o.get('truck_registration','')}</td>"
            f"<td>{o.get('driver_name','')}</td>"
            f"<td style='text-align:right'>{o.get('target_qty',0):,}</td>"
            f"<td style='text-align:right'>{o.get('loaded_qty',0):,}</td>"
            f"<td style='text-align:right'>{o.get('remaining_qty',0):,}</td>"
            f"<td>{_progress_bar_html(o.get('progress_pct',0.0))}</td>"
            f"<td>{_status_badge(o.get('status',''))}</td>"
            f"<td style='font-weight:600'>{o.get('etc_display','')}</td>"
            f"</tr>"
        )

    header_cells = "".join(f"<th>{c}</th>" for c in BOARD_COLUMNS)
    st.markdown(
        f"<table class='board-table'><thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )


# ===========================================================================
# Loading Session tab (persistent, sequential Freighter → Local)
# ===========================================================================

def _ss_get(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _session_calc(trucks_loading: int, trucks_done: int, start_time, now_local) -> dict:
    """Return a dict of derived session metrics."""
    import pytz
    tz = pytz.timezone(DISPLAY_TIMEZONE)
    session_start_dt = tz.localize(datetime.combine(date.today(), start_time))
    elapsed_hours = max((now_local - session_start_dt).total_seconds() / 3600.0, 0.0)
    trucks_remaining = max(0, trucks_loading - trucks_done)
    trucks_per_hour = (trucks_done / elapsed_hours) if (elapsed_hours > 0 and trucks_done > 0) else 1.0
    if trucks_remaining > 0:
        hours_left = trucks_remaining / trucks_per_hour
        finish_dt = now_local + timedelta(hours=hours_left)
        finish_str = finish_dt.strftime("%H:%M")
        if finish_dt.date() > now_local.date():
            finish_str += f" (+{(finish_dt.date() - now_local.date()).days}d)"
    else:
        hours_left = 0.0
        finish_str = "✅ Done"
    pct = round(trucks_done / trucks_loading * 100, 1) if trucks_loading > 0 else 0.0
    return dict(
        elapsed_hours=elapsed_hours,
        trucks_per_hour=trucks_per_hour,
        trucks_remaining=trucks_remaining,
        hours_left=hours_left,
        finish_str=finish_str,
        pct=pct,
    )


def _render_loading_session_tab(orders: list[dict]) -> None:
    """
    Two-phase sequential session tracker.
    Freighter session first, then Local.  State is held in st.session_state
    so it survives auto-refresh.
    """
    import pytz

    now_local = calculations.get_local_now()

    # Initialise session state keys
    for sess in ("freight", "local"):
        _ss_get(f"sess_{sess}_started", False)
        _ss_get(f"sess_{sess}_start_time", now_local.replace(minute=0, second=0, microsecond=0).time())
        _ss_get(f"sess_{sess}_trucks", 0)
        _ss_get(f"sess_{sess}_done", 0)
        _ss_get(f"sess_{sess}_complete", False)
        _ss_get(f"sess_{sess}_finish_str", "—")

    freight_orders = [o for o in orders if o.get("route_type") == "Freighter"]
    local_orders   = [o for o in orders if o.get("route_type") == "Local"]
    n_freight = len(freight_orders)
    n_local   = len(local_orders)

    # Summary strip
    freight_started  = st.session_state["sess_freight_started"]
    freight_complete = st.session_state["sess_freight_complete"]
    local_started    = st.session_state["sess_local_started"]
    local_complete   = st.session_state["sess_local_complete"]

    if freight_started or local_started:
        sc1, sc2 = st.columns(2)
        with sc1:
            if freight_started:
                fd = st.session_state["sess_freight_done"]
                ft = st.session_state["sess_freight_trucks"]
                fs = st.session_state["sess_freight_finish_str"]
                icon = "🔵" if freight_complete else "🟢"
                st.markdown(
                    f"<div style='background:#f0f4ff;border-left:4px solid #1B2D6B;"
                    f"padding:0.5rem 0.75rem;border-radius:6px;margin-bottom:0.5rem'>"
                    f"<b>{icon} Freighters session</b> &nbsp; {fd}/{ft} trucks loaded"
                    f"{'  — finished at ' + fs if freight_complete else ''}</div>",
                    unsafe_allow_html=True,
                )
        with sc2:
            if local_started:
                ld = st.session_state["sess_local_done"]
                lt = st.session_state["sess_local_trucks"]
                ls = st.session_state["sess_local_finish_str"]
                icon = "🔵" if local_complete else "🟢"
                st.markdown(
                    f"<div style='background:#f0fff4;border-left:4px solid #22c55e;"
                    f"padding:0.5rem 0.75rem;border-radius:6px;margin-bottom:0.5rem'>"
                    f"<b>{icon} Local Routes session</b> &nbsp; {ld}/{lt} trucks loaded"
                    f"{'  — finished at ' + ls if local_complete else ''}</div>",
                    unsafe_allow_html=True,
                )
        st.markdown("")

    # Tabs
    tab_f, tab_l = st.tabs(["🚛 Freighters Session", "🚐 Local Routes Session"])

    for sess_key, tab, label, n_trucks in [
        ("freight", tab_f, "Freighters", n_freight),
        ("local",   tab_l, "Local Routes", n_local),
    ]:
        with tab:
            started  = st.session_state[f"sess_{sess_key}_started"]
            complete = st.session_state[f"sess_{sess_key}_complete"]

            if n_trucks == 0:
                st.info(f"No {label} orders for today.")
                continue

            if not started:
                st.markdown(
                    f"<small style='color:#6b7280'>{n_trucks} {label} trucks in today's plan.</small>",
                    unsafe_allow_html=True,
                )
                col_n, col_t, col_btn = st.columns([2, 2, 1])
                with col_n:
                    init_trucks = st.number_input(
                        "Trucks in this session",
                        min_value=1, max_value=n_trucks, value=n_trucks,
                        key=f"sess_{sess_key}_init_trucks",
                    )
                with col_t:
                    init_time = st.time_input(
                        "Session start time",
                        value=now_local.replace(minute=0, second=0, microsecond=0).time(),
                        key=f"sess_{sess_key}_init_time",
                    )
                with col_btn:
                    st.markdown("<div style='margin-top:1.8rem'>", unsafe_allow_html=True)
                    if st.button("▶ Start", key=f"btn_start_{sess_key}", type="primary"):
                        st.session_state[f"sess_{sess_key}_started"] = True
                        st.session_state[f"sess_{sess_key}_trucks"] = init_trucks
                        st.session_state[f"sess_{sess_key}_start_time"] = init_time
                        st.session_state[f"sess_{sess_key}_done"] = 0
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                trucks_loading = st.session_state[f"sess_{sess_key}_trucks"]
                start_time     = st.session_state[f"sess_{sess_key}_start_time"]
                trucks_done    = st.session_state[f"sess_{sess_key}_done"]

                m = _session_calc(trucks_loading, trucks_done, start_time, now_local)

                # Live KPI row
                rc1, rc2, rc3, rc4 = st.columns(4)
                with rc1:
                    st.markdown(_kpi_card("Elapsed", f"{m['elapsed_hours']:.1f} hrs",
                        f"since {start_time.strftime('%H:%M')}"), unsafe_allow_html=True)
                with rc2:
                    st.markdown(_kpi_card("Rate", f"{m['trucks_per_hour']:.1f} /hr",
                        f"{trucks_done} done"), unsafe_allow_html=True)
                with rc3:
                    st.markdown(_kpi_card("Remaining", str(m["trucks_remaining"]),
                        f"of {trucks_loading}"), unsafe_allow_html=True)
                with rc4:
                    st.markdown(_kpi_card("Est. Finish", m["finish_str"],
                        f"≈{m['hours_left']:.1f} hrs" if m["hours_left"] > 0 else "Complete"),
                        unsafe_allow_html=True)

                st.markdown("")
                st.markdown(_progress_bar_html(m["pct"]), unsafe_allow_html=True)
                st.markdown(f"**{m['pct']:.0f}%** &nbsp; {trucks_done}/{trucks_loading} trucks", unsafe_allow_html=True)
                st.markdown("")

                # Update controls
                if not complete:
                    uc1, uc2 = st.columns([3, 2])
                    with uc1:
                        new_done = st.number_input(
                            "Trucks finished loading",
                            min_value=0, max_value=trucks_loading,
                            value=trucks_done, step=1,
                            key=f"sess_{sess_key}_done_input",
                        )
                    with uc2:
                        st.markdown("<div style='margin-top:1.8rem'>", unsafe_allow_html=True)
                        ucol1, ucol2 = st.columns(2)
                        with ucol1:
                            if st.button("Update", key=f"btn_upd_{sess_key}"):
                                st.session_state[f"sess_{sess_key}_done"] = new_done
                                st.rerun()
                        with ucol2:
                            if st.button("✅ Mark Complete", key=f"btn_done_{sess_key}"):
                                st.session_state[f"sess_{sess_key}_done"] = trucks_loading
                                st.session_state[f"sess_{sess_key}_complete"] = True
                                st.session_state[f"sess_{sess_key}_finish_str"] = now_local.strftime("%H:%M")
                                st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    if new_done == 0:
                        st.info("💡 Update trucks finished as the session progresses — the estimate will refine.")
                else:
                    st.success(f"Session complete — finished at {st.session_state[f'sess_{sess_key}_finish_str']}")
                    if st.button("🔄 Reset Session", key=f"btn_reset_{sess_key}"):
                        for k in ["started", "start_time", "trucks", "done", "complete", "finish_str"]:
                            st.session_state[f"sess_{sess_key}_{k}"] = (
                                False if k in ("started", "complete") else
                                now_local.replace(minute=0, second=0, microsecond=0).time() if k == "start_time" else
                                0 if k in ("trucks", "done") else "—"
                            )
                        st.rerun()


# ===========================================================================
# Depot loading ETC helpers (24,000 loaves/hour per truck)
# ===========================================================================

DEPOT_LOADING_RATE = 24_000  # loaves per hour, per truck (fixed)


def _truck_etc(remaining_qty: int, now_local) -> "Optional[datetime]":
    if remaining_qty <= 0:
        return None
    from datetime import timedelta
    hours = remaining_qty / DEPOT_LOADING_RATE
    return now_local + timedelta(hours=hours)


def _route_etc(group: list[dict], now_local) -> "Optional[datetime]":
    etcs = []
    for o in group:
        rem = max(0, o.get("target_qty", 0) - o.get("loaded_qty", 0))
        etc = _truck_etc(rem, now_local)
        if etc is not None:
            etcs.append(etc)
    return max(etcs) if etcs else None


def _fmt_etc(etc, now_local) -> str:
    if etc is None:
        return "Done"
    import pytz
    tz = pytz.timezone(DISPLAY_TIMEZONE)
    if etc.tzinfo is None:
        etc = tz.localize(etc)
    return etc.astimezone(tz).strftime("%H:%M")


# ===========================================================================
# DEPOT LOADING PLAN (replacement)
# ===========================================================================

def render_loading_plan(orders: list[dict], dispatch_date: date) -> None:
    """
    Two-level loading plan driven by depot_orders (SKU-level data).

    Level 1 — one row per depot with aggregated bread / confect totals,
               overall progress bar, ETC and status badge.
    Level 2 — expandable per-depot section with one row per truck showing
               per-SKU bread breakdown, confect subtotal, progress & ETC.
               Each truck row has an inline "Mark all loaded" button and
               individual SKU loaded_qty inputs inside a nested expander.
    """
    if not auth.can_edit():
        return

    depot_rows = ddb.get_depot_orders(dispatch_date)

    # Fall back to legacy dispatch_orders view if no depot_orders yet
    if not depot_rows:
        st.info(
            "No depot pre-alert data imported yet. "
            "Import the Depot Pre-alert sheet in the Import panel to enable "
            "SKU-level tracking. Showing legacy Freighter summary below."
        )
        _render_legacy_loading_plan(orders, dispatch_date)
        return

    st.markdown(
        "<small style='color:#6b7280'>"
        "Expand a depot row to see per-truck SKU breakdown. "
        "Use <b>Mark all loaded</b> to bulk-complete a truck, or adjust individual SKU quantities.</small>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Build depot → truck → sku tree ────────────────────────────────
    from collections import defaultdict
    depots: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in depot_rows:
        if r.get("truck_label") == "_TOTAL":
            continue
        depots[r["depot_name"]][r["truck_label"]].append(r)

    now_local = calculations.get_local_now()

    # ── Level-1 table header ──────────────────────────────────────────
    st.markdown(
        "<table class='board-table'><thead><tr>"
        "<th>DEPOT</th>"
        "<th style='text-align:right'>BREAD ORDER</th>"
        "<th style='text-align:right'>CONFECT ORDER</th>"
        "<th style='text-align:right'>TOTAL</th>"
        "<th style='text-align:right'>LOADED</th>"
        "<th style='text-align:right'>REMAINING</th>"
        "<th>PROGRESS</th>"
        "<th>STATUS</th>"
        "<th style='text-align:center'>EST. DONE</th>"
        "</tr></thead></tr>",
        unsafe_allow_html=True,
    )

    for depot_name, trucks in sorted(depots.items()):
        # Aggregate across all trucks for this depot
        bread_ordered   = sum(r["ordered_qty"] for trs in trucks.values() for r in trs if r["sku_group"] == "bread")
        confect_ordered = sum(r["ordered_qty"] for trs in trucks.values() for r in trs if r["sku_group"] == "confect")
        total_ordered   = bread_ordered + confect_ordered
        total_loaded    = sum(r["loaded_qty"]  for trs in trucks.values() for r in trs)
        total_rem       = max(0, total_ordered - total_loaded)
        pct             = calculations.progress_pct(total_loaded, total_ordered)

        if total_loaded == 0:
            agg_status = STATUS_IN_QUEUE
        elif total_loaded < total_ordered:
            agg_status = STATUS_LOADING
        else:
            agg_status = STATUS_LOADED

        # ETC: route ETC = slowest truck (max across trucks)
        truck_etcs = []
        for truck_label, truck_rows in trucks.items():
            truck_rem = max(0, sum(r["ordered_qty"] for r in truck_rows) - sum(r["loaded_qty"] for r in truck_rows))
            if truck_rem > 0:
                etc = now_local + timedelta(hours=truck_rem / DEPOT_LOADING_RATE)
                truck_etcs.append(etc)
        depot_etc = max(truck_etcs) if truck_etcs else None
        etc_str   = _fmt_etc(depot_etc, now_local) if agg_status != STATUS_LOADED else "Done"
        etc_color = "#166534" if etc_str == "Done" else "#1e40af"

        # Level-1 summary row (HTML table row)
        st.markdown(
            f"<table class='board-table'><tbody><tr>"
            f"<td><b>{depot_name}</b> <small style='color:#9ca3af'>({len(trucks)} truck{'s' if len(trucks)>1 else ''})</small></td>"
            f"<td style='text-align:right'>{bread_ordered:,}</td>"
            f"<td style='text-align:right'>{confect_ordered:,}</td>"
            f"<td style='text-align:right'><b>{total_ordered:,}</b></td>"
            f"<td style='text-align:right'>{total_loaded:,}</td>"
            f"<td style='text-align:right'>{total_rem:,}</td>"
            f"<td>{_progress_bar_html(pct)}</td>"
            f"<td>{_status_badge(agg_status)}</td>"
            f"<td style='text-align:center;font-weight:700;color:{etc_color}'>{etc_str}</td>"
            f"</tr></tbody></table>",
            unsafe_allow_html=True,
        )

        # Level-2: per-truck expandable detail
        with st.expander(f"🚛 Trucks — {depot_name}", expanded=False):
            for truck_label, truck_rows in sorted(trucks.items()):
                bread_rows   = sorted([r for r in truck_rows if r["sku_group"] == "bread"],   key=lambda x: x["sku_name"])
                confect_rows = sorted([r for r in truck_rows if r["sku_group"] == "confect"], key=lambda x: x["sku_name"])

                truck_ordered = sum(r["ordered_qty"] for r in truck_rows)
                truck_loaded  = sum(r["loaded_qty"]  for r in truck_rows)
                truck_rem     = max(0, truck_ordered - truck_loaded)
                truck_pct     = calculations.progress_pct(truck_loaded, truck_ordered)
                truck_reg     = next((r.get("truck_registration") for r in truck_rows if r.get("truck_registration")), "—")

                if truck_loaded == 0:
                    truck_status = STATUS_IN_QUEUE
                elif truck_loaded < truck_ordered:
                    truck_status = STATUS_LOADING
                else:
                    truck_status = STATUS_LOADED

                t_etc = (now_local + timedelta(hours=truck_rem / DEPOT_LOADING_RATE)) if truck_rem > 0 else None
                t_etc_str = _fmt_etc(t_etc, now_local) if truck_status != STATUS_LOADED else "Done"

                st.markdown(
                    f"<table class='board-table'><tbody><tr>"
                    f"<td style='width:18%'><b>{truck_label}</b></td>"
                    f"<td style='width:12%;color:#6b7280'>{truck_reg}</td>"
                    f"<td style='width:30%'>{_progress_bar_html(truck_pct)}</td>"
                    f"<td style='width:15%'>{_status_badge(truck_status)}</td>"
                    f"<td style='width:10%;text-align:right'>{truck_loaded:,} / {truck_ordered:,}</td>"
                    f"<td style='width:15%;text-align:center;font-weight:700;color:{'#166534' if t_etc_str=='Done' else '#1e40af'}'>{t_etc_str}</td>"
                    f"</tr></tbody></table>",
                    unsafe_allow_html=True,
                )

                # Mark-all-loaded button for this truck
                col_btn, col_info = st.columns([1, 4])
                with col_btn:
                    if st.button(
                        "✅ Mark all loaded",
                        key=f"depot_allloaded_{depot_name}_{truck_label}",
                        help=f"Mark all SKUs on {truck_label} as fully loaded",
                    ):
                        for r in truck_rows:
                            if r["ordered_qty"] > 0:
                                ddb.update_depot_loaded_qty(r["id"], r["ordered_qty"], auth.current_user())
                        st.success(f"{truck_label}: all SKUs marked as loaded.")
                        st.rerun()
                with col_info:
                    st.markdown(
                        f"<small style='color:#6b7280'>{len(truck_rows)} SKUs · "
                        f"{sum(r['ordered_qty'] for r in bread_rows):,} bread · "
                        f"{sum(r['ordered_qty'] for r in confect_rows):,} confect</small>",
                        unsafe_allow_html=True,
                    )

                # Per-SKU adjustment expander
                with st.expander(f"Adjust SKU quantities — {truck_label}", expanded=False):
                    st.markdown("**Bread SKUs**")
                    for r in bread_rows:
                        if r["ordered_qty"] == 0:
                            continue
                        sk1, sk2, sk3 = st.columns([2, 1.5, 1.5])
                        with sk1:
                            st.markdown(r["sku_name"])
                        with sk2:
                            st.markdown(f"Ordered: **{r['ordered_qty']:,}**")
                        with sk3:
                            new_val = st.number_input(
                                "Loaded",
                                min_value=0,
                                max_value=r["ordered_qty"] * 2,
                                value=r["loaded_qty"],
                                step=50,
                                key=f"sku_loaded_{r['id']}",
                                label_visibility="collapsed",
                            )
                            if new_val != r["loaded_qty"]:
                                ddb.update_depot_loaded_qty(r["id"], new_val, auth.current_user())
                                st.rerun()

                    if confect_rows:
                        st.markdown("**Confect SKUs**")
                        for r in confect_rows:
                            if r["ordered_qty"] == 0:
                                continue
                            ck1, ck2, ck3 = st.columns([2, 1.5, 1.5])
                            with ck1:
                                st.markdown(r["sku_name"])
                            with ck2:
                                st.markdown(f"Ordered: **{r['ordered_qty']:,}**")
                            with ck3:
                                new_val = st.number_input(
                                    "Loaded",
                                    min_value=0,
                                    max_value=r["ordered_qty"] * 2,
                                    value=r["loaded_qty"],
                                    step=50,
                                    key=f"sku_loaded_{r['id']}",
                                    label_visibility="collapsed",
                                )
                                if new_val != r["loaded_qty"]:
                                    ddb.update_depot_loaded_qty(r["id"], new_val, auth.current_user())
                                    st.rerun()

                st.markdown("---")


def _render_legacy_loading_plan(orders: list[dict], dispatch_date: date) -> None:
    """Unchanged legacy loading plan — shown when no depot_orders exist yet."""
    freighter_orders = [o for o in orders if o.get("route_type") == "Freighter"]
    if not freighter_orders:
        st.info("No Freighter / depot orders for today.")
        return

    from collections import defaultdict
    route_groups: dict = defaultdict(list)
    for o in freighter_orders:
        route_groups[o["route_name"]].append(o)

    st.markdown(
        "<table class='board-table'><thead><tr>"
        "<th>ROUTE</th><th style='text-align:right'>TARGET</th>"
        "<th>PROGRESS</th><th>STATUS</th><th style='text-align:center'>EST. DONE</th>"
        "</tr></thead></table>",
        unsafe_allow_html=True,
    )
    now_local = calculations.get_local_now()
    for route_name, group in sorted(route_groups.items()):
        total_target = sum(o.get("target_qty", 0) for o in group)
        total_loaded = sum(o.get("loaded_qty", 0) for o in group)
        pct = calculations.progress_pct(total_loaded, total_target)
        rem = max(0, total_target - total_loaded)
        etc = (now_local + timedelta(hours=rem / DEPOT_LOADING_RATE)) if rem > 0 else None
        etc_str = _fmt_etc(etc, now_local)
        if total_loaded == 0:
            status = STATUS_IN_QUEUE
        elif total_loaded < total_target:
            status = STATUS_LOADING
        else:
            status = STATUS_LOADED
        st.markdown(
            f"<table class='board-table'><tbody><tr>"
            f"<td><b>{route_name}</b></td>"
            f"<td style='text-align:right'>{total_target:,}</td>"
            f"<td>{_progress_bar_html(pct)}</td>"
            f"<td>{_status_badge(status)}</td>"
            f"<td style='text-align:center;font-weight:700'>{etc_str}</td>"
            f"</tr></tbody></table>",
            unsafe_allow_html=True,
        )


# ===========================================================================
# DEPOT IMPORT PANEL (new)
# ===========================================================================

def render_depot_import_panel(dispatch_date: date) -> None:
    """
    Panel for importing the Depot Pre-Alert Excel sheet.
    Parses per-depot, per-truck, per-SKU quantities into depot_orders table.
    """
    if not auth.can_upload():
        return

    st.markdown("---")
    st.subheader("📦 Import Depot Pre-Alert Sheet")
    st.markdown(
        "<small style='color:#6b7280'>Upload the daily depot pre-alert workbook. "
        "Each depot sheet is parsed separately — truck sub-routes and per-SKU quantities "
        "are extracted from the Loading Breakdown section of each sheet.</small>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Upload Depot Pre-Alert Excel (.xlsx)",
        type=["xlsx"],
        key="depot_upload",
        help="Each depot sheet must contain a '▸  LOADING BREAKDOWN' section.",
    )

    if uploaded is None:
        return

    file_bytes = uploaded.read()
    with st.spinner("Parsing depot pre-alert sheet…"):
        rows, warnings = parse_depot_excel(file_bytes, dispatch_date)

    if warnings:
        for w in warnings:
            st.warning(w)

    if not rows:
        st.error("No valid depot order rows found in the uploaded file.")
        return

    # ── Preview grouped by depot / truck ──────────────────────────────
    from collections import defaultdict as _dd
    by_depot: dict = _dd(lambda: _dd(list))
    for r in rows:
        by_depot[r["depot_name"]][r["truck_label"]].append(r)

    total_bread = sum(r["ordered_qty"] for r in rows if r["sku_group"] == "bread")
    total_confect = sum(r["ordered_qty"] for r in rows if r["sku_group"] == "confect")
    depot_count = len(by_depot)
    truck_count = sum(len(trucks) for trucks in by_depot.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Depots", depot_count)
    c2.metric("Truck Sub-routes", truck_count)
    c3.metric("Total Bread", f"{total_bread:,}")
    c4.metric("Total Confect", f"{total_confect:,}")

    with st.expander("Preview by depot / truck", expanded=True):
        for depot_name, trucks in sorted(by_depot.items()):
            st.markdown(f"**{depot_name}**")
            preview_rows = []
            for truck_label, skus in sorted(trucks.items()):
                bread_total = sum(r["ordered_qty"] for r in skus if r["sku_group"] == "bread")
                confect_total = sum(r["ordered_qty"] for r in skus if r["sku_group"] == "confect")
                truck_reg = next((r["truck_registration"] for r in skus if r.get("truck_registration")), "—")
                preview_rows.append({
                    "Truck": truck_label,
                    "Reg": truck_reg or "—",
                    "Bread SKUs": len([r for r in skus if r["sku_group"] == "bread"]),
                    "Bread Qty": bread_total,
                    "Confect SKUs": len([r for r in skus if r["sku_group"] == "confect"]),
                    "Confect Qty": confect_total,
                    "Total Qty": bread_total + confect_total,
                })
            import pandas as pd
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    col_confirm, col_replace, col_clear = st.columns([2, 2, 1])

    with col_confirm:
        if st.button("✅ Confirm Import (merge)", type="primary", use_container_width=True,
                     help="Upsert rows — existing trucks keep their loaded_qty; new trucks are added."):
            with st.spinner("Saving depot orders…"):
                inserted, errors = ddb.upsert_depot_orders(rows)
            if errors:
                st.warning(f"Imported {inserted} rows with {errors} errors.")
            else:
                st.success(f"{inserted} depot order rows upserted successfully.")
            st.rerun()

    with col_replace:
        if st.button("🔄 Replace (clear then import)", use_container_width=True,
                     help="Delete ALL depot orders for today first, then import fresh."):
            with st.spinner("Replacing depot orders…"):
                ddb.delete_depot_orders_for_date(dispatch_date)
                inserted, errors = ddb.upsert_depot_orders(rows)
            if errors:
                st.warning(f"Replaced with {inserted} rows ({errors} errors).")
            else:
                st.success(f"Replaced — {inserted} depot order rows imported.")
            st.rerun()

    with col_clear:
        if st.button("🗑 Clear Depot Orders", use_container_width=True):
            ddb.delete_depot_orders_for_date(dispatch_date)
            st.success("Depot orders cleared.")
            st.rerun()


# ===========================================================================
# TV SLIDE 2 DEPOT (replacement for slide index 1)
# ===========================================================================

def _tv_slide2_depot(dispatch_date: date, freighter_fallback: list[dict]) -> None:
    """
    TV Slide 2 — Depot Loading Board driven by depot_orders.

    Shows one row per depot: DEPOT | BREAD ORDER | CONFECT ORDER | TOTAL |
    LOADED | REMAINING | PROGRESS | STATUS | EST. DONE

    Banner at top shows the latest all-depots finish estimate.
    Falls back to the legacy freighter-order view if no depot_orders exist.
    """
    st.markdown("### 📋 Depot Loading Board")

    depot_summary = ddb.get_depot_summary(dispatch_date)

    if not depot_summary:
        # ── Fallback to legacy view ───────────────────────────────────
        if freighter_fallback:
            tv_now = calculations.get_local_now()
            from collections import defaultdict
            groups: dict = defaultdict(list)
            for o in freighter_fallback:
                groups[o["route_name"]].append(o)

            rows_html = ""
            all_etcs = []
            for route_name, group in sorted(groups.items()):
                total_target = sum(o.get("target_qty", 0) for o in group)
                total_loaded = sum(o.get("loaded_qty", 0) for o in group)
                total_rem = max(0, total_target - total_loaded)
                pct = calculations.progress_pct(total_loaded, total_target)
                if total_loaded == 0:
                    agg_status = STATUS_IN_QUEUE
                elif total_loaded < total_target:
                    agg_status = STATUS_LOADING
                else:
                    agg_status = STATUS_LOADED
                # ETC per route (slowest truck in group)
                r_etc_parts = []
                for o in group:
                    rem = max(0, o.get("target_qty", 0) - o.get("loaded_qty", 0))
                    if rem > 0:
                        r_etc_parts.append(tv_now + timedelta(hours=rem / DEPOT_LOADING_RATE))
                r_etc = max(r_etc_parts) if r_etc_parts else None
                if r_etc:
                    all_etcs.append(r_etc)
                r_etc_str = _fmt_etc(r_etc, tv_now) if agg_status != STATUS_LOADED else "Done"
                etc_color = "#166534" if r_etc_str == "Done" else "#1e40af"
                rows_html += (
                    f"<tr>"
                    f"<td><b>{route_name}</b></td>"
                    f"<td colspan='2' style='text-align:right'>—</td>"
                    f"<td style='text-align:right'>{total_target:,}</td>"
                    f"<td style='text-align:right'>{total_loaded:,}</td>"
                    f"<td style='text-align:right'>{total_rem:,}</td>"
                    f"<td>{_progress_bar_html(pct)}</td>"
                    f"<td>{_status_badge(agg_status)}</td>"
                    f"<td style='text-align:center;font-weight:700;color:{etc_color}'>{r_etc_str}</td>"
                    f"</tr>"
                )
            _render_tv_depot_table(rows_html, all_etcs, tv_now)
        else:
            st.info("No freighter orders for today.")
        return

    # ── Depot summary from depot_orders ──────────────────────────────
    tv_now = calculations.get_local_now()
    rows_html = ""
    all_etcs = []

    for d in depot_summary:
        pct = d["progress_pct"]
        total_rem = max(0, d["total_ordered"] - d["total_loaded"])

        # ETC: use full depot total remaining at 24,000/hr * parallel trucks
        effective_rate = DEPOT_LOADING_RATE * max(1, d["truck_count"])
        if total_rem > 0:
            d_etc = tv_now + timedelta(hours=total_rem / effective_rate)
            all_etcs.append(d_etc)
        else:
            d_etc = None

        d_etc_str = _fmt_etc(d_etc, tv_now) if d["status"] != STATUS_LOADED else "Done"
        etc_color = "#166534" if d_etc_str == "Done" else "#1e40af"

        rows_html += (
            f"<tr>"
            f"<td><b>{d['depot_name']}</b></td>"
            f"<td style='text-align:right'>{d['bread_ordered']:,}</td>"
            f"<td style='text-align:right'>{d['confect_ordered']:,}</td>"
            f"<td style='text-align:right'><b>{d['total_ordered']:,}</b></td>"
            f"<td style='text-align:right'>{d['total_loaded']:,}</td>"
            f"<td style='text-align:right'>{total_rem:,}</td>"
            f"<td>{_progress_bar_html(pct)}</td>"
            f"<td>{_status_badge(d['status'])}</td>"
            f"<td style='text-align:center;font-weight:700;color:{etc_color}'>{d_etc_str}</td>"
            f"</tr>"
        )

    _render_tv_depot_table(rows_html, all_etcs, tv_now)


def _render_tv_depot_table(rows_html: str, all_etcs: list, tv_now) -> None:
    """Render the banner + HTML table for the TV depot board."""
    if all_etcs:
        all_done_str = "All depots done by " + _fmt_etc(max(all_etcs), tv_now)
        banner_color = "#1B2D6B"
    else:
        all_done_str = "✅ All depots loaded"
        banner_color = "#166534"

    st.markdown(
        f"<div style='background:#f0f4ff;border-left:5px solid {banner_color};"
        f"padding:0.5rem 1rem;border-radius:6px;margin-bottom:0.75rem;"
        f"font-size:1.2rem;font-weight:700;color:{banner_color}'>"
        f"⏱ {all_done_str}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<table class='board-table'><thead><tr>"
        "<th>DEPOT</th>"
        "<th style='text-align:right'>BREAD ORDER</th>"
        "<th style='text-align:right'>CONFECT ORDER</th>"
        "<th style='text-align:right'>TOTAL</th>"
        "<th style='text-align:right'>LOADED</th>"
        "<th style='text-align:right'>REMAINING</th>"
        "<th>PROGRESS</th>"
        "<th>STATUS</th>"
        "<th style='text-align:center'>EST. DONE</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )


# ===========================================================================
# Supervisor controls — update loaded qty / status
# ===========================================================================

def render_supervisor_controls(orders: list[dict], dispatch_date: date) -> None:
    if not auth.can_edit():
        return

    st.markdown("---")
    st.subheader("Supervisor Controls")

    tab_session, tab_update, tab_create, tab_settings = st.tabs(
        ["Loading Session", "Update Order", "New Order", "Production Settings"]
    )

    # ── Loading Session ETC ───────────────────────────────────────────────
    with tab_session:
        _render_loading_session_tab(orders)

    # ── Update Order ─────────────────────────────────────────────────────
    with tab_update:
        if not orders:
            st.info("No orders to update.")
        else:
            route_map = {
                f"{o['route_name']} ({o.get('truck_registration','')})": o["id"]
                for o in orders
            }
            selected_label = st.selectbox("Select Route", list(route_map.keys()), key="upd_route")
            order_id = route_map[selected_label]
            order = next((o for o in orders if o["id"] == order_id), None)

            if order:
                col_a, col_b = st.columns(2)
                with col_a:
                    new_loaded = st.number_input(
                        "Loaded Qty",
                        min_value=0,
                        max_value=order["target_qty"] * 2,
                        value=order["loaded_qty"],
                        step=50,
                        key="upd_loaded",
                    )
                with col_b:
                    all_opts = ALL_STATUSES
                    current_idx = all_opts.index(order["status"]) if order["status"] in all_opts else 0
                    new_status = st.selectbox(
                        "Override Status", all_opts, index=current_idx, key="upd_status"
                    )

                if st.button("Save Changes", key="btn_save_order"):
                    changed = False
                    if new_loaded != order["loaded_qty"]:
                        ok = db.update_loaded_qty(order_id, new_loaded, auth.current_user())
                        if ok:
                            st.success(f"Loaded qty updated to {new_loaded:,}")
                            changed = True
                        else:
                            st.error("Failed to update loaded qty.")

                    auto_status = calculations.derive_status(new_loaded, order["target_qty"])
                    if new_status != auto_status and new_status != order["status"]:
                        ok2 = db.update_status(order_id, new_status, auth.current_user())
                        if ok2:
                            st.success(f"Status overridden to {new_status}")
                            changed = True
                        else:
                            st.error("Failed to update status.")

                    if changed:
                        st.rerun()

    # ── Create Order ─────────────────────────────────────────────────────
    with tab_create:
        with st.form("create_order_form"):
            route_name = st.text_input("Route Name", placeholder="e.g. MUTARE 5")
            route_type = st.selectbox("Route Type", ["Local", "Freighter"])
            driver = st.text_input("Driver Name")
            truck = st.text_input("Truck Registration")
            target = st.number_input("Target Qty", min_value=0, step=50)
            submitted = st.form_submit_button("New Order")

        if submitted:
            if not route_name:
                st.error("Route name is required.")
            else:
                new_order = {
                    "dispatch_date": dispatch_date.isoformat(),
                    "route_name": route_name.strip().upper(),
                    "route_type": route_type,
                    "driver_name": driver.strip() or "TBA",
                    "truck_registration": truck.strip() or "TBA",
                    "target_qty": int(target),
                    "loaded_qty": 0,
                    "status": STATUS_IN_QUEUE,
                }
                row = db.create_single_order(new_order, auth.current_user())
                if row:
                    st.success(f"Order created: {route_name.upper()}")
                    st.rerun()
                else:
                    st.error("Failed to create order.")

    # ── Production Settings ───────────────────────────────────────────────
    with tab_settings:
        settings = db.get_settings()
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            new_buffer = st.number_input(
                "Opening Stock (loaves in bin at start of shift)",
                min_value=0,
                value=settings["current_bin_level"],
                step=500,
                key="set_buffer",
            )
        with col_s2:
            new_rate = st.number_input(
                "Hourly Production Rate (loaves/hour)",
                min_value=1,
                value=settings["hourly_production_rate"],
                step=100,
                key="set_rate",
            )

        if st.button("Save Settings", key="btn_save_settings"):
            ok = db.update_settings(
                current_bin_level=int(new_buffer),
                hourly_production_rate=int(new_rate),
                changed_by=auth.current_user(),
            )
            if ok:
                st.success("Settings saved.")
                st.rerun()
            else:
                st.error("Failed to save settings.")


# ===========================================================================
# Import panel (main orders)
# ===========================================================================

def render_import_panel(dispatch_date: date) -> None:
    if not auth.can_upload():
        return

    st.markdown("---")
    st.subheader("Import Daily Order Sheet")

    uploaded = st.file_uploader(
        "Upload Excel order sheet (.xlsx)",
        type=["xlsx"],
        key="order_upload",
        help="Upload the daily Excel workbook. Both 'Orders' and 'Confect Orders' sheets are parsed.",
    )

    if uploaded is None:
        return

    file_bytes = uploaded.read()
    with st.spinner("Parsing order sheet…"):
        orders, warnings = parse_all_sheets(file_bytes, dispatch_date)

    if warnings:
        for w in warnings:
            st.warning(w)

    if not orders:
        st.error("No valid orders found in the uploaded file.")
        return

    st.success(f"Found **{len(orders)}** valid orders")

    # Preview
    preview_df = pd.DataFrame(orders)[
        ["route_name", "route_type", "driver_name", "truck_registration", "target_qty"]
    ].rename(
        columns={
            "route_name": "Route",
            "route_type": "Type",
            "driver_name": "Driver",
            "truck_registration": "Truck",
            "target_qty": "Target Qty",
        }
    )
    st.dataframe(preview_df, use_container_width=True, height=300)

    total = sum(o["target_qty"] for o in orders)
    freighters = [o for o in orders if o["route_type"] == "Freighter"]
    locals_ = [o for o in orders if o["route_type"] == "Local"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Demand", f"{total:,}")
    col2.metric("Freighter Routes", len(freighters))
    col3.metric("Local Routes", len(locals_))

    col_confirm, col_clear = st.columns([2, 1])
    with col_confirm:
        if st.button("Confirm Import", type="primary", use_container_width=True):
            with st.spinner("Saving orders…"):
                # Only delete Local orders — Freighter orders are entered manually
                # and must not be overwritten by an Excel re-import.
                db.delete_orders_for_date(dispatch_date, route_type="Local")
                inserted, errors = db.bulk_insert_orders(orders)
            if errors:
                st.warning(f"Imported {inserted} orders with {errors} errors.")
            else:
                st.success(f"{inserted} orders imported successfully. Freighter orders preserved.")
            st.rerun()
    with col_clear:
        if st.button("Clear Today's Orders", use_container_width=True):
            db.delete_orders_for_date(dispatch_date)
            st.success("Today's orders cleared.")
            st.rerun()

    # === DEPOT IMPORT PANEL CALLED HERE ===
    render_depot_import_panel(dispatch_date)


# ===========================================================================
# Charts
# ===========================================================================

def render_charts(orders: list[dict]) -> None:
    if not orders:
        return

    st.markdown("---")
    st.subheader("Analytics")

    chart_tab1, chart_tab2, chart_tab3 = st.tabs(
        ["Demand by Route", "Loading Progress", "Status Distribution"]
    )

    with chart_tab1:
        df_chart = pd.DataFrame(orders)[["route_name", "route_type", "target_qty", "loaded_qty"]]
        df_chart = df_chart.sort_values("target_qty", ascending=False).head(30)
        fig = px.bar(
            df_chart,
            x="route_name",
            y=["target_qty", "loaded_qty"],
            barmode="overlay",
            labels={"route_name": "Route", "value": "Loaves", "variable": ""},
            color_discrete_map={"target_qty": "#cbd5e1", "loaded_qty": "#22c55e"},
            title="Target vs Loaded Quantity (Top 30 Routes)",
        )
        fig.update_layout(xaxis_tickangle=-45, height=400, margin=dict(l=0, r=0, t=40, b=100))
        st.plotly_chart(fig, use_container_width=True)

    with chart_tab2:
        augmented = calculations.augment_orders(orders, 5000)
        df_prog = pd.DataFrame(augmented)[["route_name", "progress_pct", "route_type"]]
        df_prog = df_prog.sort_values("progress_pct", ascending=True)
        fig2 = px.bar(
            df_prog,
            x="progress_pct",
            y="route_name",
            orientation="h",
            color="route_type",
            color_discrete_map={"Freighter": "#6366f1", "Local": "#22c55e"},
            labels={"progress_pct": "Progress %", "route_name": "Route"},
            title="Loading Progress by Route",
        )
        fig2.update_layout(height=max(400, len(df_prog) * 22), margin=dict(l=0, r=0, t=40, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    with chart_tab3:
        status_counts = pd.Series([o.get("status", STATUS_IN_QUEUE) for o in orders]).value_counts()
        fig3 = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Orders by Status",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.update_traces(textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True)


# ===========================================================================
# CSV Export
# ===========================================================================

def render_export(orders: list[dict]) -> None:
    if not orders or not auth.can_edit():
        return
    df_export = pd.DataFrame(orders)
    csv = df_export.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"dispatch_{date.today().isoformat()}.csv",
        mime="text/csv",
        key="csv_dl",
    )


# ===========================================================================
# Audit trail tab
# ===========================================================================

def render_audit_trail() -> None:
    if not auth.is_admin():
        st.info("Audit trail is available to admin users only.")
        return

    st.subheader("Audit Trail")
    history = db.get_history(limit=300)
    if not history:
        st.info("No audit records found.")
        return

    df_hist = pd.DataFrame(history)[
        ["created_at", "action", "changed_by", "old_value", "new_value", "dispatch_order_id"]
    ]
    df_hist["created_at"] = pd.to_datetime(df_hist["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(df_hist, use_container_width=True, height=400)


# ===========================================================================
# User management (admin)
# ===========================================================================

def render_user_management() -> None:
    if not auth.is_admin():
        return

    st.subheader("User Management")

    users = db.list_users()
    if users:
        df_users = pd.DataFrame(users)[["username", "role", "created_at"]]
        df_users["created_at"] = pd.to_datetime(df_users["created_at"]).dt.strftime(
            "%Y-%m-%d %H:%M"
        )
        st.dataframe(df_users, use_container_width=True)

    st.markdown("**Add new user**")
    with st.form("add_user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["viewer", "supervisor", "admin"])
        create_btn = st.form_submit_button("Create User")

    if create_btn:
        if not new_username or not new_password:
            st.error("Username and password are required.")
        else:
            hashed = auth.hash_password(new_password)
            row = db.create_user(new_username.strip(), hashed, new_role)
            if row:
                st.success(f"User '{new_username}' created.")
                st.rerun()
            else:
                st.error("Failed to create user (may already exist).")


# ===========================================================================
# Search
# ===========================================================================

def render_search(dispatch_date: date, hourly_rate: int) -> None:
    st.subheader("Search Orders")
    query = st.text_input("Search by route, truck, or driver", placeholder="e.g. MUTARE or AGP0188")
    if query:
        results = db.search_orders(dispatch_date, query)
        if results:
            augmented = calculations.augment_orders(results, hourly_rate)
            render_board_tab(augmented, hourly_rate, False, "Search Results")
        else:
            st.info(f"No orders matching '{query}'.")


# ===========================================================================
# TV display mode
# ===========================================================================

def render_tv_mode(orders: list[dict], settings: dict) -> None:
    """
    Full-screen TV display — cycles through three slides every 15 s.
    Slide 1: KPI cards
    Slide 2: Loading Plan (Freighter / depot orders only)
    Slide 3: Dispatch board (Freighters tab)
    Auto-refresh every 30 s keeps data live.
    """
    import time as _time

    tv_css = """
    <style>
    #MainMenu, footer, header, [data-testid="stSidebar"] { display:none !important; }
    .block-container { padding: 0.5rem 1rem !important; max-width:100% !important; }
    h1 { font-size: 3rem !important; }
    .board-table { font-size: 1.1rem; }
    .board-table th { font-size: 1rem; }
    .tv-slide-indicator { text-align:center; font-size:0.85rem; color:#9ca3af; margin-top:0.5rem; }
    </style>
    """
    st.markdown(tv_css, unsafe_allow_html=True)

    now_local = calculations.get_local_now()
    now_str = now_local.strftime("%A %d %B %Y  %H:%M")

    # Header (always shown)
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;justify-content:center;gap:1.5rem;padding:0.5rem 0 0.75rem 0;'>
            <img src='{_LOGO_B64}' alt='Baker\'s Inn' style='height:60px;width:auto;' />
            <div>
                <div style='font-size:1.8rem;font-weight:800;color:#1B2D6B;line-height:1.1;'>Dispatch Board</div>
                <div style='font-size:1rem;color:#C9A84C;font-weight:700;letter-spacing:1px;text-transform:uppercase;'>{now_str}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hourly_rate = settings.get("hourly_production_rate", 5000)
    freighters  = [o for o in orders if o.get("route_type") == "Freighter"]
    locals_     = [o for o in orders if o.get("route_type") == "Local"]

    # Determine current slide from wall clock (15-second rotation)
    SLIDE_SECONDS = 15
    slide_index = (int(now_local.timestamp()) // SLIDE_SECONDS) % 3

    slide_placeholder = st.empty()

    with slide_placeholder.container():
        if slide_index == 0:
            # ── Slide 1: KPI cards ──────────────────────────────────────
            st.markdown("### 📊 Operations Overview")
            render_kpi_cards(orders, settings)
            # Session summaries if active
            for sess_key, label in [("freight", "Freighters"), ("local", "Local Routes")]:
                if st.session_state.get(f"sess_{sess_key}_started"):
                    done = st.session_state.get(f"sess_{sess_key}_done", 0)
                    total = st.session_state.get(f"sess_{sess_key}_trucks", 0)
                    finish = st.session_state.get(f"sess_{sess_key}_finish_str", "—")
                    complete = st.session_state.get(f"sess_{sess_key}_complete", False)
                    icon = "🔵" if complete else "🟢"
                    st.markdown(
                        f"<div style='background:#f8f9fa;border-left:4px solid #1B2D6B;"
                        f"padding:0.4rem 0.75rem;border-radius:6px;font-size:1rem;margin-top:0.4rem'>"
                        f"<b>{icon} {label}</b> &nbsp; {done}/{total} trucks loaded"
                        f"{'  · finished at ' + finish if complete else ''}</div>",
                        unsafe_allow_html=True,
                    )

        elif slide_index == 1:
            # ── Slide 2: Depot loading board (replacement) ───────────────
            _tv_slide2_depot(date.today(), freighters)

        else:
            # ── Slide 3: Local routes board ─────────────────────────────
            st.markdown("### 🚐 Local Routes Board")
            render_board_tab(locals_, hourly_rate, True, "Local")

    # Slide indicator dots
    dots = " &nbsp; ".join(
        f"<span style='color:{'#1B2D6B' if i==slide_index else '#d1d5db'};font-size:1.4rem;'>●</span>"
        for i in range(3)
    )
    labels = ["Overview", "Loading Plan", "Local Routes"]
    st.markdown(
        f"<div class='tv-slide-indicator'>{dots} &nbsp; <b>{labels[slide_index]}</b> "
        f"· auto-advances every {SLIDE_SECONDS}s</div>",
        unsafe_allow_html=True,
    )


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    tv_mode = _is_tv_mode()
    _inject_css(tv_mode)

    # ── Authentication ──────────────────────────────────────────────────
    auth.require_auth()

    # ── Auto-refresh ────────────────────────────────────────────────────
    st_autorefresh(interval=AUTOREFRESH_MS, key="dispatch_autorefresh")

    # ── Dispatch date ────────────────────────────────────────────────────
    today = date.today()

    # ── Load data ────────────────────────────────────────────────────────
    settings = db.get_settings()
    hourly_rate = settings.get("hourly_production_rate", 5000)

    if tv_mode:
        orders = db.get_orders_for_date(today)
        render_tv_mode(orders, settings)
        return

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f"""
            <div class='bi-sidebar-brand'>
                <img src='{_LOGO_B64}' alt='Baker\'s Inn' />
                <p class='bi-sidebar-sub'>Dispatch Control Tower</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**User:** {auth.current_user()}")
        st.markdown(f"**Role:** `{auth.current_role()}`")
        st.markdown(f"**Date:** {today.strftime('%d %b %Y')}")

        st.markdown("---")
        dispatch_date = st.date_input("Dispatch Date", value=today)

        st.markdown("---")
        nav = st.radio(
            "Navigation",
            ["Dashboard", "Search", "Audit Trail", "Users"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            auth.logout()
            st.rerun()

        st.markdown("---")
        st.markdown(
            "<small style='color:#9ca3af'>TV mode: add <code>?display=true</code> to URL</small>",
            unsafe_allow_html=True,
        )

    # ── Load orders for selected date ────────────────────────────────────
    orders = db.get_orders_for_date(dispatch_date)
    freighters = [o for o in orders if o.get("route_type") == "Freighter"]
    locals_ = [o for o in orders if o.get("route_type") == "Local"]

    # ── Dashboard ────────────────────────────────────────────────────────
    if nav == "Dashboard":
        st.markdown(
            f"""
            <div class='bi-page-header'>
                <img src='{_LOGO_B64}' alt='Baker\'s Inn' />
                <div>
                    <p class='bi-page-header-title'>Dispatch Control Tower</p>
                    <p class='bi-page-header-sub'>{dispatch_date.strftime('%A, %d %B %Y')} &nbsp;&middot;&nbsp; Refreshes every 30 seconds</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # KPIs
        render_kpi_cards(orders, settings)
        st.markdown("")

        # Import panel (includes both main order import and depot import)
        render_import_panel(dispatch_date)

        # Airport board
        st.markdown("---")
        st.subheader("Dispatch Board")

        col_exp, col_dl = st.columns([8, 2])
        with col_dl:
            render_export(orders)

        board_tab_f, board_tab_l = st.tabs(["Freighters", "Local Routes"])
        with board_tab_f:
            render_board_tab(freighters, hourly_rate, False, "Freighter")
        with board_tab_l:
            render_board_tab(locals_, hourly_rate, False, "Local")

        # Loading Plan (depots / freighters only) - replaced with depot version
        st.markdown("---")
        with st.expander("📋 Loading Plan — Freighter / Depot Trucks", expanded=False):
            render_loading_plan(orders, dispatch_date)

        # Supervisor controls
        render_supervisor_controls(orders, dispatch_date)

        # Charts
        render_charts(orders)
        _render_pulse_footer()

    elif nav == "Search":
        st.title("Search Orders")
        render_search(dispatch_date, hourly_rate)
        _render_pulse_footer()

    elif nav == "Audit Trail":
        st.title("Audit Trail")
        render_audit_trail()
        _render_pulse_footer()

    elif nav == "Users":
        st.title("User Management")
        render_user_management()
        _render_pulse_footer()


if __name__ == "__main__":
    main()
