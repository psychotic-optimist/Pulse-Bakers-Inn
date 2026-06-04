"""
calculations.py — Dispatch timing and KPI calculations for Bakery Dispatch Control Tower.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

import pytz

from config import DISPLAY_TIMEZONE


def get_local_now() -> datetime:
    """Return current datetime in the bakery's local timezone."""
    tz = pytz.timezone(DISPLAY_TIMEZONE)
    return datetime.now(tz)


def derive_status(loaded_qty: int, target_qty: int) -> str:
    """Return automatic status string based on quantities."""
    from config import STATUS_IN_QUEUE, STATUS_LOADING, STATUS_LOADED  # noqa: PLC0415
    if loaded_qty == 0:
        return STATUS_IN_QUEUE
    if loaded_qty < target_qty:
        return STATUS_LOADING
    return STATUS_LOADED


def remaining_qty(target_qty: int, loaded_qty: int) -> int:
    """Quantity still to be loaded."""
    return max(0, target_qty - loaded_qty)


def loading_duration_hours(rem_qty: int, hourly_rate: int) -> float:
    """Hours needed to load *rem_qty* at *hourly_rate* loaves/hour."""
    if hourly_rate <= 0:
        return float("inf")
    return rem_qty / hourly_rate


def estimated_completion_time(
    rem_qty: int,
    hourly_rate: int,
    as_of: Optional[datetime] = None,
) -> Optional[datetime]:
    """Return the estimated completion datetime, or None if already done."""
    if rem_qty <= 0:
        return None
    if hourly_rate <= 0:
        return None
    if as_of is None:
        as_of = get_local_now()
    duration = timedelta(hours=loading_duration_hours(rem_qty, hourly_rate))
    return as_of + duration


def format_etc(etc: Optional[datetime]) -> str:
    """Format ETC for display on the airport board."""
    if etc is None:
        return "✅ Done"
    tz = pytz.timezone(DISPLAY_TIMEZONE)
    if etc.tzinfo is None:
        etc = tz.localize(etc)
    return etc.astimezone(tz).strftime("%H:%M")


def progress_pct(loaded_qty: int, target_qty: int) -> float:
    """Return loading progress as a 0–100 float."""
    if target_qty <= 0:
        return 0.0
    return min(100.0, round(loaded_qty / target_qty * 100, 1))


# ---------------------------------------------------------------------------
# KPI aggregates
# ---------------------------------------------------------------------------

def kpi_total_demand(orders: list[dict]) -> int:
    return sum(o.get("target_qty", 0) for o in orders)


def kpi_total_loaded(orders: list[dict]) -> int:
    return sum(o.get("loaded_qty", 0) for o in orders)


def kpi_total_remaining(orders: list[dict]) -> int:
    return sum(remaining_qty(o.get("target_qty", 0), o.get("loaded_qty", 0)) for o in orders)


def kpi_overall_progress(orders: list[dict]) -> float:
    demand = kpi_total_demand(orders)
    loaded = kpi_total_loaded(orders)
    return progress_pct(loaded, demand)


def kpi_estimated_finish(
    orders: list[dict],
    hourly_rate: int,
    current_buffer: int,
) -> Optional[datetime]:
    """Estimate when ALL remaining orders will be loaded."""
    total_rem = max(0, kpi_total_remaining(orders) - current_buffer)
    return estimated_completion_time(total_rem, hourly_rate)


def augment_orders(orders: list[dict], hourly_rate: int) -> list[dict]:
    """
    Return a copy of *orders* with computed columns added:
      remaining_qty, progress_pct, etc_display
    """
    now = get_local_now()
    result = []
    for o in orders:
        rem = remaining_qty(o.get("target_qty", 0), o.get("loaded_qty", 0))
        etc = estimated_completion_time(rem, hourly_rate, as_of=now)
        result.append(
            {
                **o,
                "remaining_qty": rem,
                "progress_pct": progress_pct(o.get("loaded_qty", 0), o.get("target_qty", 0)),
                "etc_display": format_etc(etc),
            }
        )
    return result
