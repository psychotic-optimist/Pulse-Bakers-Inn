"""
database.py — Supabase data-access layer for Bakery Dispatch Control Tower.

All public functions return plain Python dicts / lists of dicts so that the
rest of the application is decoupled from the Supabase client specifics.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    """Return a cached Supabase client, reading credentials from secrets."""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def _db() -> Client:
    return _get_client()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user_by_username(username: str) -> Optional[dict]:
    """Return the user row for *username*, or None."""
    try:
        resp = (
            _db()
            .table("users")
            .select("id, username, password_hash, role, created_at")
            .eq("username", username)
            .limit(1)
            .execute()
        )
        rows = resp.data
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("get_user_by_username error: %s", exc)
        return None


def create_user(username: str, password_hash: str, role: str) -> Optional[dict]:
    """Insert a new user. Returns the created row or None on error."""
    try:
        resp = (
            _db()
            .table("users")
            .insert({"username": username, "password_hash": password_hash, "role": role})
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.error("create_user error: %s", exc)
        return None


def list_users() -> list[dict]:
    """Return all users (without password hashes)."""
    try:
        resp = (
            _db()
            .table("users")
            .select("id, username, role, created_at")
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("list_users error: %s", exc)
        return []


def delete_user(user_id: str) -> bool:
    try:
        _db().table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as exc:
        logger.error("delete_user error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Dispatch settings
# ---------------------------------------------------------------------------

def get_settings() -> dict:
    """Return the singleton dispatch settings row."""
    try:
        resp = (
            _db()
            .table("dispatch_settings")
            .select("*")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return {"id": 1, "current_bin_level": 0, "hourly_production_rate": 5000}
    except Exception as exc:
        logger.error("get_settings error: %s", exc)
        return {"id": 1, "current_bin_level": 0, "hourly_production_rate": 5000}


def update_settings(
    current_bin_level: Optional[int] = None,
    hourly_production_rate: Optional[int] = None,
    changed_by: str = "system",
) -> bool:
    """Patch the dispatch settings row and write audit entries."""
    try:
        old = get_settings()
        patch: dict = {"updated_at": datetime.utcnow().isoformat()}

        if current_bin_level is not None and current_bin_level != old["current_bin_level"]:
            patch["current_bin_level"] = current_bin_level
            _write_settings_audit(
                "buffer_update",
                str(old["current_bin_level"]),
                str(current_bin_level),
                changed_by,
            )

        if (
            hourly_production_rate is not None
            and hourly_production_rate != old["hourly_production_rate"]
        ):
            patch["hourly_production_rate"] = hourly_production_rate
            _write_settings_audit(
                "production_rate_update",
                str(old["hourly_production_rate"]),
                str(hourly_production_rate),
                changed_by,
            )

        if len(patch) > 1:  # more than just updated_at
            _db().table("dispatch_settings").update(patch).eq("id", 1).execute()
        return True
    except Exception as exc:
        logger.error("update_settings error: %s", exc)
        return False


def _write_settings_audit(
    action: str, old_value: str, new_value: str, changed_by: str
) -> None:
    try:
        _db().table("dispatch_history").insert(
            {
                "dispatch_order_id": "00000000-0000-0000-0000-000000000000",
                "action": action,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
            }
        ).execute()
    except Exception as exc:
        logger.warning("_write_settings_audit failed: %s", exc)


# ---------------------------------------------------------------------------
# Dispatch orders
# ---------------------------------------------------------------------------

def get_orders_for_date(dispatch_date: date) -> list[dict]:
    """Return all orders for a given date, ordered by route_type then route_name."""
    try:
        resp = (
            _db()
            .table("dispatch_orders")
            .select("*")
            .eq("dispatch_date", dispatch_date.isoformat())
            .order("route_type")
            .order("route_name")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error("get_orders_for_date error: %s", exc)
        return []


def get_order_by_id(order_id: str) -> Optional[dict]:
    try:
        resp = (
            _db()
            .table("dispatch_orders")
            .select("*")
            .eq("id", order_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.error("get_order_by_id error: %s", exc)
        return None


def bulk_insert_orders(orders: list[dict]) -> tuple[int, int]:
    """
    Insert a list of order dicts.  Returns (inserted_count, error_count).
    Each dict must have: dispatch_date, route_name, route_type,
    driver_name, truck_registration, target_qty, loaded_qty, status.
    """
    inserted = 0
    errors = 0
    for order in orders:
        try:
            _db().table("dispatch_orders").insert(order).execute()
            inserted += 1
        except Exception as exc:
            logger.error("bulk_insert_orders row error: %s | row=%s", exc, order)
            errors += 1
    return inserted, errors


def delete_orders_for_date(dispatch_date: date) -> bool:
    """Remove all orders for *dispatch_date* (used before re-import)."""
    try:
        _db().table("dispatch_orders").delete().eq(
            "dispatch_date", dispatch_date.isoformat()
        ).execute()
        return True
    except Exception as exc:
        logger.error("delete_orders_for_date error: %s", exc)
        return False


def update_loaded_qty(
    order_id: str,
    new_qty: int,
    changed_by: str = "system",
) -> bool:
    """Update loaded_qty and auto-derive status; write audit entry."""
    try:
        old = get_order_by_id(order_id)
        if old is None:
            return False

        new_status = _derive_status(new_qty, old["target_qty"])
        _db().table("dispatch_orders").update(
            {"loaded_qty": new_qty, "status": new_status}
        ).eq("id", order_id).execute()

        _write_order_audit(
            order_id, "loaded_qty_update",
            str(old["loaded_qty"]), str(new_qty), changed_by
        )
        if new_status != old["status"]:
            _write_order_audit(
                order_id, "status_auto_update",
                old["status"], new_status, changed_by
            )
        return True
    except Exception as exc:
        logger.error("update_loaded_qty error: %s", exc)
        return False


def update_status(
    order_id: str,
    new_status: str,
    changed_by: str = "system",
) -> bool:
    """Manually override the status; write audit entry."""
    try:
        old = get_order_by_id(order_id)
        if old is None:
            return False

        _db().table("dispatch_orders").update({"status": new_status}).eq(
            "id", order_id
        ).execute()

        _write_order_audit(
            order_id, "status_manual_override",
            old["status"], new_status, changed_by
        )
        return True
    except Exception as exc:
        logger.error("update_status error: %s", exc)
        return False


def create_single_order(order: dict, changed_by: str = "system") -> Optional[dict]:
    """Insert a single order and write an audit entry."""
    try:
        resp = _db().table("dispatch_orders").insert(order).execute()
        row = resp.data[0] if resp.data else None
        if row:
            _write_order_audit(
                row["id"], "order_created", None,
                f"route={order.get('route_name')}, qty={order.get('target_qty')}",
                changed_by,
            )
        return row
    except Exception as exc:
        logger.error("create_single_order error: %s", exc)
        return None


def get_history(order_id: Optional[str] = None, limit: int = 200) -> list[dict]:
    """Return audit history, optionally filtered to a single order."""
    try:
        q = (
            _db()
            .table("dispatch_history")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if order_id:
            q = q.eq("dispatch_order_id", order_id)
        return q.execute().data or []
    except Exception as exc:
        logger.error("get_history error: %s", exc)
        return []


def search_orders(
    dispatch_date: date,
    query: str,
) -> list[dict]:
    """Full-text search across route_name, truck_registration, driver_name."""
    all_orders = get_orders_for_date(dispatch_date)
    q = query.lower()
    return [
        o for o in all_orders
        if q in (o.get("route_name") or "").lower()
        or q in (o.get("truck_registration") or "").lower()
        or q in (o.get("driver_name") or "").lower()
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_status(loaded_qty: int, target_qty: int) -> str:
    from config import STATUS_IN_QUEUE, STATUS_LOADING, STATUS_LOADED  # noqa: PLC0415
    if loaded_qty == 0:
        return STATUS_IN_QUEUE
    if loaded_qty < target_qty:
        return STATUS_LOADING
    return STATUS_LOADED


def _write_order_audit(
    order_id: str,
    action: str,
    old_value: Optional[str],
    new_value: Optional[str],
    changed_by: str,
) -> None:
    try:
        _db().table("dispatch_history").insert(
            {
                "dispatch_order_id": order_id,
                "action": action,
                "old_value": old_value,
                "new_value": new_value,
                "changed_by": changed_by,
            }
        ).execute()
    except Exception as exc:
        logger.warning("_write_order_audit failed: %s", exc)
