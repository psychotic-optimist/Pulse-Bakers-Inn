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
# Supervisor controls — update loaded qty / status
# ===========================================================================

# ===========================================================================
# Session state helpers
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
# Loading Session tab (persistent, sequential Freighter → Local)
# ===========================================================================

def render_loading_plan(orders: list[dict], dispatch_date: date) -> None:
    """
    Aggregated loading plan for Freighter (depot) trucks.

    Each *route* is shown as one row even when multiple truck orders exist.
    The supervisor sets a single BREAD QTY for the whole route; the total is
    distributed proportionally across the underlying truck orders on Save.
    Per-truck checkboxes and adjustment popovers live inside an expander.
    """
    if not auth.can_edit():
        return

    freighter_orders = [o for o in orders if o.get("route_type") == "Freighter"]
    if not freighter_orders:
        st.info("No Freighter / depot orders for today.")
        return

    st.markdown(
        "<small style='color:#6b7280'>Tick a truck to mark it <b>fully loaded</b>. "
        "Use <b>⚙️ Adjust</b> to correct the actual quantity loaded. "
        "<i>CONFECT QTY column is reserved — separate confect quantities require a "
        "schema migration.</i></small>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Group orders by route_name ──────────────────────────────────────
    from collections import defaultdict as _dd
    route_groups = _dd(list)
    for o in freighter_orders:
        route_groups[o["route_name"]].append(o)

    # Table header
    st.markdown(
        "<table class='board-table'><thead><tr>"
        "<th>ROUTE</th>"
        "<th style='text-align:right'>ORDER</th>"
        "<th>DRIVER</th>"
        "<th>TRUCK</th>"
        "<th style='text-align:right'>BREAD QTY</th>"
        "<th style='text-align:center'>CONFECT QTY</th>"
        "<th>PROGRESS</th>"
        "<th>STATUS</th>"
        "</tr></thead></table>",
        unsafe_allow_html=True,
    )

    any_changed = False

    for route_name, group in sorted(route_groups.items()):
        total_target = sum(o.get("target_qty", 0) for o in group)
        total_loaded = sum(o.get("loaded_qty", 0) for o in group)
        pct = calculations.progress_pct(total_loaded, total_target)
        if total_loaded == 0:
            agg_status = STATUS_IN_QUEUE
        elif total_loaded < total_target:
            agg_status = STATUS_LOADING
        else:
            agg_status = STATUS_LOADED

        first_driver = next(
            (o.get("driver_name", "TBA") for o in group if o.get("driver_name") not in ("TBA", "", None)), "TBA"
        )
        first_truck = next(
            (o.get("truck_registration", "TBA") for o in group if o.get("truck_registration") not in ("TBA", "", None)), "TBA"
        )

        qty_key = f"lp_qty_{route_name}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = total_target

        col_route, col_order, col_driver, col_truck, col_qty, col_confect, col_prog, col_stat, col_save, col_all = st.columns(
            [2, 1.2, 1.8, 1.5, 1.4, 1.2, 2, 1.8, 1, 1.2]
        )

        with col_route:
            st.markdown(f"**{route_name}**")
        with col_order:
            st.markdown(f"<div style='text-align:right'>{total_target:,}</div>", unsafe_allow_html=True)
        with col_driver:
            st.markdown(first_driver)
        with col_truck:
            st.markdown(first_truck)
        with col_qty:
            new_total = st.number_input(
                "Bread Qty",
                min_value=0,
                value=st.session_state[qty_key],
                step=100,
                key=f"lp_qty_input_{route_name}",
                label_visibility="collapsed",
                help=f"Set the total bread target for all trucks on route {route_name}.",
            )
            st.session_state[qty_key] = new_total
        with col_confect:
            st.markdown(
                "<div style='text-align:center;color:#9ca3af' "
                "title='Confect QTY not yet implemented — separate schema required'>—</div>",
                unsafe_allow_html=True,
            )
        with col_prog:
            st.markdown(_progress_bar_html(pct), unsafe_allow_html=True)
        with col_stat:
            st.markdown(_status_badge(agg_status), unsafe_allow_html=True)
        with col_save:
            if st.button("Save", key=f"lp_save_{route_name}"):
                # Distribute new_total proportionally across truck orders
                n = len(group)
                base = new_total // n
                remainder = new_total % n
                for idx, o in enumerate(group):
                    truck_qty = base + (1 if idx < remainder else 0)
                    try:
                        db._db().table("dispatch_orders").update(
                            {"target_qty": truck_qty}
                        ).eq("id", o["id"]).execute()
                        db._write_order_audit(
                            o["id"], "target_qty_updated",
                            str(o.get("target_qty", 0)), str(truck_qty),
                            auth.current_user(),
                        )
                    except Exception as exc:
                        st.error(f"Failed to save {route_name}: {exc}")
                st.success(f"{route_name}: target set to {new_total:,} across {n} truck(s).")
                any_changed = True
        with col_all:
            if st.button(
                "All Loaded", key=f"lp_allloaded_{route_name}",
                help=f"Mark all trucks in {route_name} as fully loaded",
            ):
                for o in group:
                    db.update_loaded_qty(o["id"], o.get("target_qty", 0), auth.current_user())
                st.success(f"{route_name}: all trucks marked as loaded.")
                any_changed = True

        # Per-truck expand for fine-grained checkbox / adjust
        with st.expander(f"Trucks ({len(group)}) — {route_name}", expanded=False):
            for o in group:
                oid = o["id"]
                target = o.get("target_qty", 0)
                loaded = o.get("loaded_qty", 0)
                _ss_get(f"lp_checked_{oid}", loaded >= target and target > 0)
                tc1, tc2, tc3, tc4, tc5, tc6 = st.columns([1.5, 1.5, 1, 1, 2, 1])
                with tc1:
                    checked = st.checkbox(
                        f"{o.get('truck_registration', 'TBA')}",
                        value=st.session_state[f"lp_checked_{oid}"],
                        key=f"lp_cb_{oid}",
                    )
                with tc2:
                    st.markdown(o.get("driver_name", "TBA"))
                with tc3:
                    st.markdown(f"T: {target:,}")
                with tc4:
                    st.markdown(f"L: {loaded:,}")
                with tc5:
                    st.markdown(_progress_bar_html(calculations.progress_pct(loaded, target)), unsafe_allow_html=True)
                with tc6:
                    with st.popover("⚙️ Adjust"):
                        adj = st.number_input(
                            "Adjustment",
                            min_value=-target, max_value=target * 2,
                            value=0, step=50,
                            key=f"lp_adj_{oid}",
                        )
                        if st.button("Apply", key=f"lp_adjbtn_{oid}"):
                            current = db.get_order_by_id(oid)
                            if current:
                                new_qty = max(0, current["loaded_qty"] + adj)
                                ok = db.update_loaded_qty(oid, new_qty, auth.current_user())
                                if ok:
                                    st.success(f"Set loaded = {new_qty:,}")
                                    any_changed = True

                prev_checked = st.session_state[f"lp_checked_{oid}"]
                if checked and not prev_checked:
                    if db.update_loaded_qty(oid, target, auth.current_user()):
                        st.session_state[f"lp_checked_{oid}"] = True
                        any_changed = True
                elif not checked and prev_checked:
                    if db.update_loaded_qty(oid, 0, auth.current_user()):
                        st.session_state[f"lp_checked_{oid}"] = False
                        any_changed = True

        st.markdown("<hr style='margin:4px 0;border-color:#f1f5f9'>", unsafe_allow_html=True)

    if any_changed:
        st.rerun()

    st.markdown("")
    if st.button("✅ Mark ALL Freighters as Loaded", key="lp_bulk_load"):
        count = 0
        for o in freighter_orders:
            if o.get("loaded_qty", 0) < o.get("target_qty", 0):
                db.update_loaded_qty(o["id"], o["target_qty"], auth.current_user())
                st.session_state[f"lp_checked_{o['id']}"] = True
                count += 1
        if count:
            st.success(f"Marked {count} freighter trucks as fully loaded.")
            st.rerun()

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
# Import panel
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
            # ── Slide 2: Aggregated depot table (read-only) ─────────────
            st.markdown("### 📋 Depot Loading Plan")
            if freighters:
                # Aggregate by route_name, same logic as interactive Loading Plan
                from collections import defaultdict as _tvdd
                tv_groups = _tvdd(list)
                for o in freighters:
                    tv_groups[o["route_name"]].append(o)

                rows_html = ""
                for route_name, group in sorted(tv_groups.items()):
                    total_target = sum(o.get("target_qty", 0) for o in group)
                    total_loaded = sum(o.get("loaded_qty", 0) for o in group)
                    total_rem    = max(0, total_target - total_loaded)
                    pct = calculations.progress_pct(total_loaded, total_target)
                    if total_loaded == 0:
                        agg_status = STATUS_IN_QUEUE
                    elif total_loaded < total_target:
                        agg_status = STATUS_LOADING
                    else:
                        agg_status = STATUS_LOADED
                    first_driver = next(
                        (o.get("driver_name", "—") for o in group if o.get("driver_name") not in ("TBA", "", None)), "—"
                    )
                    first_truck = next(
                        (o.get("truck_registration", "—") for o in group if o.get("truck_registration") not in ("TBA", "", None)), "—"
                    )
                    rows_html += (
                        f"<tr>"
                        f"<td><b>{route_name}</b></td>"
                        f"<td>{first_driver}</td>"
                        f"<td>{first_truck}</td>"
                        f"<td style='text-align:right'>{total_target:,}</td>"
                        f"<td style='text-align:right'>{total_loaded:,}</td>"
                        f"<td style='text-align:right'>{total_rem:,}</td>"
                        f"<td>{_progress_bar_html(pct)}</td>"
                        f"<td>{_status_badge(agg_status)}</td>"
                        f"</tr>"
                    )
                st.markdown(
                    "<table class='board-table'><thead><tr>"
                    "<th>ROUTE</th><th>DRIVER</th><th>TRUCK</th>"
                    "<th style='text-align:right'>TARGET</th>"
                    "<th style='text-align:right'>LOADED</th>"
                    "<th style='text-align:right'>REMAINING</th>"
                    "<th>PROGRESS</th><th>STATUS</th>"
                    f"</tr></thead><tbody>{rows_html}</tbody></table>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("No freighter orders for today.")

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

# TV display mode
# ===========================================================================


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

        # Import panel
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

        # Loading Plan (depots / freighters only)
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
