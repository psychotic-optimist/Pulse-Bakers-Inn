"""
depot_database.py — Supabase data-access layer for depot SKU-level orders.
Table: depot_orders
  id, dispatch_date, depot_name, truck_label, truck_registration,
  sku_name, sku_group, ordered_qty, loaded_qty, status,
  created_at, updated_at
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Optional

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def _db() -> Client:
    return _get_client()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_depot_orders(dispatch_date: date) -> list[dict]:
    """All depot_orders rows for a given date."""
    try:
        resp = (
            _db()
            .table("depot_orders")
            .select("*")
            .eq("dispatch_date", dispatch_date.isoformat())
            .order("depot_name")
            .order("truck_label")
            .order("sku_name")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("get_depot_orders error: %s", exc)
        return []


def get_depot_orders_by_depot(dispatch_date: date, depot_name: str) -> list[dict]:
    try:
        resp = (
            _db()
            .table("depot_orders")
            .select("*")
            .eq("dispatch_date", dispatch_date.isoformat())
            .eq("depot_name", depot_name.upper())
            .order("truck_label")
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
    Bulk upsert rows into depot_orders using the unique constraint
    (dispatch_date, depot_name, truck_label, sku_name).
    Returns (upserted_count, error_count).
    """
    upserted = 0
    errors = 0
    # Batch in chunks of 100 to avoid payload limits
    chunk_size = 100
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        try:
            _db().table("depot_orders").upsert(
                chunk,
                on_conflict="dispatch_date,depot_name,truck_label,sku_name",
            ).execute()
            upserted += len(chunk)
        except Exception as exc:
            logger.error("upsert_depot_orders chunk error: %s", exc)
            errors += len(chunk)
    return upserted, errors


def update_depot_loaded_qty(row_id: str, new_qty: int, changed_by: str = "system") -> bool:
    try:
        row = (
            _db()
            .table("depot_orders")
            .select("*")
            .eq("id", row_id)
            .limit(1)
            .execute()
        ).data
        if not row:
            return False
        old = row[0]
        ordered = old.get("ordered_qty", 0)
        if new_qty <= 0:
            status = "In Queue"
        elif new_qty < ordered:
            status = "Loading"
        else:
            status = "Loaded"
        _db().table("depot_orders").update(
            {"loaded_qty": new_qty, "status": status}
        ).eq("id", row_id).execute()
        # Audit via dispatch_history table if accessible
        try:
            _db().table("dispatch_history").insert({
                "dispatch_order_id": "00000000-0000-0000-0000-000000000001",
                "action": "depot_loaded_qty_update",
                "old_value": str(old.get("loaded_qty", 0)),
                "new_value": str(new_qty),
                "changed_by": changed_by,
            }).execute()
        except Exception:
            pass
        return True
    except Exception as exc:
        logger.error("update_depot_loaded_qty error: %s", exc)
        return False


def delete_depot_orders_for_date(dispatch_date: date, depot_name: Optional[str] = None) -> bool:
    try:
        q = _db().table("depot_orders").delete().eq(
            "dispatch_date", dispatch_date.isoformat()
        )
        if depot_name:
            q = q.eq("depot_name", depot_name.upper())
        q.execute()
        return True
    except Exception as exc:
        logger.error("delete_depot_orders_for_date error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Aggregated summary
# ---------------------------------------------------------------------------

def get_depot_summary(dispatch_date: date) -> list[dict]:
    """
    Returns one dict per depot_name with aggregated totals and truck list.
    """
    rows = get_depot_orders(dispatch_date)
    if not rows:
        return []

    by_depot: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_depot[r["depot_name"]].append(r)

    summaries = []
    for depot_name, depot_rows in sorted(by_depot.items()):
        bread_ordered   = sum(r["ordered_qty"] for r in depot_rows if r["sku_group"] == "bread")
        bread_loaded    = sum(r["loaded_qty"]  for r in depot_rows if r["sku_group"] == "bread")
        confect_ordered = sum(r["ordered_qty"] for r in depot_rows if r["sku_group"] == "confect")
        confect_loaded  = sum(r["loaded_qty"]  for r in depot_rows if r["sku_group"] == "confect")
        total_ordered   = bread_ordered + confect_ordered
        total_loaded    = bread_loaded  + confect_loaded
        pct = round(total_loaded / total_ordered * 100, 1) if total_ordered > 0 else 0.0
        trucks = sorted({r["truck_label"] for r in depot_rows})
        summaries.append({
            "depot_name":       depot_name,
            "bread_ordered":    bread_ordered,
            "bread_loaded":     bread_loaded,
            "confect_ordered":  confect_ordered,
            "confect_loaded":   confect_loaded,
            "total_ordered":    total_ordered,
            "total_loaded":     total_loaded,
            "progress_pct":     pct,
            "trucks":           trucks,
            "rows":             depot_rows,
        })
    return summaries
