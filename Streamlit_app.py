"""
streamlit_app_depot_additions.py
=================================
Drop-in additions / replacements for Streamlit_app.py.

HOW TO INTEGRATE
----------------
1. Add this import near the top of Streamlit_app.py (with the other imports):

    import depot_database as ddb
    from depot_importer import parse_depot_excel

2. Replace the existing render_loading_plan() function with
   render_loading_plan() from this file.

3. Replace the `elif slide_index == 1:` block inside render_tv_mode()
   with the equivalent block from _tv_slide2_depot() in this file.

4. Add a call to render_depot_import_panel() inside the existing
   render_import_panel() function (or call it from a new tab in the
   supervisor panel).

The complete, standalone versions of all three additions are below.
"""

from __future__ import annotations

# ── These imports are already in Streamlit_app.py — listed here for clarity ──
from datetime import date, datetime, timedelta
from typing import Optional
from collections import defaultdict

import streamlit as st

import calculations
import database as db
import depot_database as ddb
import dispatch_auth as auth
from depot_importer import parse_depot_excel
from config import (
    DISPLAY_TIMEZONE,
    STATUS_IN_QUEUE,
    STATUS_LOADING,
    STATUS_LOADED,
)

# DEPOT_LOADING_RATE is already defined in Streamlit_app.py as 24_000
# _progress_bar_html, _status_badge, _fmt_etc, _route_etc are already in Streamlit_app.py

# ===========================================================================
# 1. render_depot_import_panel()
# ===========================================================================

def render_depot_import_panel(dispatch_date: date) -> None:
    """
    Panel for importing the Depot Pre-Alert Excel sheet.
    Parses per-depot, per-truck, per-SKU quantities into depot_orders table.
    Add a call to this function inside render_import_panel() or a new tab.
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
# 2. render_loading_plan() — replacement using depot_orders
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
            "Import the Depot Pre-Alert sheet in the Import panel to enable "
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
        "</tr></thead></table>",
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
                etc = now_local + timedelta(hours=truck_rem / 24_000)
                truck_etcs.append(etc)
        depot_etc = max(truck_etcs) if truck_etcs else None
        etc_str   = _fmt_etc_local(depot_etc, now_local) if agg_status != STATUS_LOADED else "Done"
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

                t_etc = (now_local + timedelta(hours=truck_rem / 24_000)) if truck_rem > 0 else None
                t_etc_str = _fmt_etc_local(t_etc, now_local) if truck_status != STATUS_LOADED else "Done"

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
        etc = (now_local + timedelta(hours=rem / 24_000)) if rem > 0 else None
        etc_str = _fmt_etc_local(etc, now_local)
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
# 3. TV Slide 2 replacement — _tv_slide2_depot()
# ===========================================================================
# Replace the `elif slide_index == 1:` block in render_tv_mode() with:
#
#   elif slide_index == 1:
#       _tv_slide2_depot(dispatch_date, freighters)
#
# and add _tv_slide2_depot() to the module.

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
                        r_etc_parts.append(tv_now + timedelta(hours=rem / 24_000))
                r_etc = max(r_etc_parts) if r_etc_parts else None
                if r_etc:
                    all_etcs.append(r_etc)
                r_etc_str = _fmt_etc_local(r_etc, tv_now) if agg_status != STATUS_LOADED else "Done"
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
            _render_tv_depot_table(rows_html, all_etcs, calculations.get_local_now())
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

        # ETC: use full depot total remaining at 24,000/hr
        # (truck_count determines parallelism — but we only have depot-level
        #  aggregates here; use truck_count as parallel factor)
        effective_rate = 24_000 * max(1, d["truck_count"])
        if total_rem > 0:
            d_etc = tv_now + timedelta(hours=total_rem / effective_rate)
            all_etcs.append(d_etc)
        else:
            d_etc = None

        d_etc_str = _fmt_etc_local(d_etc, tv_now) if d["status"] != STATUS_LOADED else "Done"
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
        all_done_str = "All depots done by " + _fmt_etc_local(max(all_etcs), tv_now)
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


# ---------------------------------------------------------------------------
# Local helper — avoids dependency on the private _fmt_etc in Streamlit_app.py
# ---------------------------------------------------------------------------

def _fmt_etc_local(etc: Optional[datetime], now_local) -> str:
    """Format ETC datetime as HH:MM, '✅ Done', or '—'."""
    if etc is None:
        return "Done"
    import pytz
    tz = pytz.timezone(DISPLAY_TIMEZONE)
    if etc.tzinfo is None:
        etc = tz.localize(etc)
    return etc.astimezone(tz).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Stubs for helpers already in Streamlit_app.py — referenced here for clarity
# These are NOT redefined; the references above assume they exist in scope
# when this code is integrated into Streamlit_app.py.
# ---------------------------------------------------------------------------

def _progress_bar_html(pct: float) -> str:  # already in Streamlit_app.py
    raise NotImplementedError("Use the version already defined in Streamlit_app.py")

def _status_badge(status: str) -> str:      # already in Streamlit_app.py
    raise NotImplementedError("Use the version already defined in Streamlit_app.py")
