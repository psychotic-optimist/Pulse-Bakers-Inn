"""
depot_database.py — Supabase data-access layer for depot_orders.

Handles SKU-level loading data imported from the depot pre-alert Excel sheets.
All public functions return plain Python dicts / lists so the rest of the app
stays decoupled from Supabase client specifics.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import streamlit as st
from supabase import Client

logger = logging.getLogger(__name__)

TABLE = "depot_orders"


# ---------------------------------------------------------------------------
# Client — reuse the singleton from database.py
# ---------------------------------------------------------------------------

def _db() -> Client:
    from database import _get_client  # noqa: PLC0415
    return _get_client()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_depot_orders(dispatch_date: date) -> list[dict]:
    """Return all depot_orders rows for *dispatch_date*, ordered by depot then truck."""
    try:
        resp = (
            _db()
            .table(TABLE)
            .select("*")
            .eq("dispatch_date", dispatch_date.isoformat())
            .order("depot_name")
            .order("truck_label")
            .order("sku_group")
            .order("sku_name")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("get_depot_orders error: %s", exc)
        return []


def get_depot_orders_by_depot(dispatch_date: date, depot_name: str) -> list[dict]:
    """Return all rows for one depot on *dispatch_date*."""
    try:
        resp = (
            _db()
            .table(TABLE)
            .select("*")
            .eq("dispatch_date", dispatch_date.isoformat())
            .eq("depot_name", depot_name)
            .order("truck_label")
            .order("sku_group")
            .order("sku_name")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("get_depot_orders_by_depot error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_depot_orders(rows: list[dict]) -> tuple[int, int]:
    """
    Bulk upsert a list of depot_order dicts using the unique constraint
    (dispatch_date, depot_name, truck_label, sku_name).

    Returns (upserted_count, error_count).
    """
    if not rows:
        return 0, 0

    upserted = 0
    errors = 0

    # Supabase Python client upsert accepts a list; batch in chunks of 500
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        try:
            _db().table(TABLE).upsert(
                chunk,
                on_conflict="dispatch_date,depot_name,truck_label,sku_name",
            ).execute()
            upserted += len(chunk)
        except Exception as exc:
            logger.error("upsert_depot_orders chunk %d error: %s", i // CHUNK, exc)
            errors += len(chunk)

    return upserted, errors


def update_depot_loaded_qty(
    row_id: str,
    new_qty: int,
    changed_by: str = "system",
) -> bool:
    """Update loaded_qty + auto-derive status + write audit entry."""
    try:
        resp = (
            _db()
            .table(TABLE)
            .select("*")
            .eq("id", row_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            logger.warning("update_depot_loaded_qty: row %s not found", row_id)
            return False

        old = resp.data[0]
        new_status = _derive_status(new_qty, old["ordered_qty"])

        _db().table(TABLE).update(
            {"loaded_qty": new_qty, "status": new_status}
        ).eq("id", row_id).execute()

        _write_audit(row_id, "loaded_qty_update", str(old["loaded_qty"]), str(new_qty), changed_by)
        if new_status != old["status"]:
            _write_audit(row_id, "status_auto_update", old["status"], new_status, changed_by)

        return True
    except Exception as exc:
        logger.error("update_depot_loaded_qty error: %s", exc)
        return False


def delete_depot_orders_for_date(
    dispatch_date: date,
    depot_name: Optional[str] = None,
) -> bool:
    """
    Delete depot_orders for *dispatch_date*.
    If *depot_name* is given, only that depot is deleted.
    """
    try:
        q = _db().table(TABLE).delete().eq("dispatch_date", dispatch_date.isoformat())
        if depot_name:
            q = q.eq("depot_name", depot_name)
        q.execute()
        return True
    except Exception as exc:
        logger.error("delete_depot_orders_for_date error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def get_depot_summary(dispatch_date: date) -> list[dict]:
    """
    Return one summary dict per depot for *dispatch_date*:

        depot_name, total_ordered, bread_ordered, confect_ordered,
        total_loaded, bread_loaded, confect_loaded,
        progress_pct, truck_count, status
    """
    rows = get_depot_orders(dispatch_date)
    if not rows:
        return []

    from collections import defaultdict as _dd

    depots: dict[str, dict] = {}
    for r in rows:
        if r.get("truck_label") == "_TOTAL":
            continue  # skip synthetic total rows
        dn = r["depot_name"]
        if dn not in depots:
            depots[dn] = {
                "depot_name": dn,
                "total_ordered": 0,
                "bread_ordered": 0,
                "confect_ordered": 0,
                "total_loaded": 0,
                "bread_loaded": 0,
                "confect_loaded": 0,
                "trucks": set(),
            }
        d = depots[dn]
        oq = r.get("ordered_qty", 0) or 0
        lq = r.get("loaded_qty", 0) or 0
        d["total_ordered"] += oq
        d["total_loaded"] += lq
        d["trucks"].add(r["truck_label"])
        if r.get("sku_group") == "bread":
            d["bread_ordered"] += oq
            d["bread_loaded"] += lq
        else:
            d["confect_ordered"] += oq
            d["confect_loaded"] += lq

    summary = []
    for dn, d in sorted(depots.items()):
        total_o = d["total_ordered"]
        total_l = d["total_loaded"]
        pct = round(total_l / total_o * 100, 1) if total_o > 0 else 0.0
        if total_l == 0:
            status = "In Queue"
        elif total_l < total_o:
            status = "Loading"
        else:
            status = "Loaded"
        summary.append({
            "depot_name": dn,
            "total_ordered": total_o,
            "bread_ordered": d["bread_ordered"],
            "confect_ordered": d["confect_ordered"],
            "total_loaded": total_l,
            "bread_loaded": d["bread_loaded"],
            "confect_loaded": d["confect_loaded"],
            "progress_pct": pct,
            "truck_count": len(d["trucks"]),
            "status": status,
        })
    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_status(loaded_qty: int, ordered_qty: int) -> str:
    from config import STATUS_IN_QUEUE, STATUS_LOADING, STATUS_LOADED  # noqa: PLC0415
    if loaded_qty <= 0:
        return STATUS_IN_QUEUE
    if loaded_qty < ordered_qty:
        return STATUS_LOADING
    return STATUS_LOADED


def _write_audit(
    row_id: str,
    action: str,
    old_value: Optional[str],
    new_value: Optional[str],
    changed_by: str,
) -> None:
    """Write to dispatch_history for audit trail (best-effort)."""
    try:
        _db().table("dispatch_history").insert(
            {
                "dispatch_order_id": row_id,
                "action": f"depot_{action}",
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
            }
        ).execute()
    except Exception as exc:
        logger.warning("depot _write_audit failed: %s", exc)
