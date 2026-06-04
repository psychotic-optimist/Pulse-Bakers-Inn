"""
importer.py — Excel order-sheet parser for Bakery Dispatch Control Tower.

Reads the bakery's daily Excel workbook (Orders / Confect Orders sheets),
cleans rows, classifies route types, and returns a list of order dicts
ready to be inserted into dispatch_orders.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime
from typing import Union

import pandas as pd

from config import FREIGHTERS, SUMMARY_ROW_KEYWORDS, STATUS_IN_QUEUE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"AREA", "DRIVER", "TRUCK", "TOTAL"}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_order_sheet(
    file_obj: Union[bytes, io.BytesIO],
    dispatch_date: date,
    sheet_name: str = "Orders",
) -> tuple[list[dict], list[str]]:
    """
    Parse *file_obj* (bytes or BytesIO of an .xlsx workbook).

    Returns
    -------
    orders : list[dict]
        Clean list of order dicts ready for insertion.
    warnings : list[str]
        Non-fatal issues encountered during parsing.
    """
    warnings: list[str] = []

    try:
        df_raw = pd.read_excel(file_obj, sheet_name=sheet_name, header=None)
    except Exception as exc:
        msg = f"Failed to read sheet '{sheet_name}': {exc}"
        logger.error(msg)
        return [], [msg]

    # ------------------------------------------------------------------
    # 1. Locate the header row (contains "AREA" and "TOTAL")
    # ------------------------------------------------------------------
    header_row_idx = _find_header_row(df_raw)
    if header_row_idx is None:
        w = f"Could not find header row (expecting 'AREA' and 'TOTAL') in sheet '{sheet_name}'."
        logger.warning(w)
        return [], [w]

    df = df_raw.iloc[header_row_idx:].copy()
    df.columns = [str(c).strip().upper() if not str(c).startswith("Unnamed") else f"_COL{i}"
                  for i, c in enumerate(df_raw.iloc[header_row_idx])]
    df = df.iloc[1:].reset_index(drop=True)  # drop header row itself

    # ------------------------------------------------------------------
    # 2. Normalise column names to canonical set
    # ------------------------------------------------------------------
    col_map = _build_column_map(df.columns.tolist())
    missing = REQUIRED_COLUMNS - set(col_map.values())
    if missing:
        w = f"Missing required columns: {missing}. Found: {df.columns.tolist()}"
        logger.warning(w)
        warnings.append(w)

    df = df.rename(columns={v: v for v in df.columns})  # identity; done via col_map below
    df_work = _extract_working_df(df, col_map)

    # ------------------------------------------------------------------
    # 3. Drop blank / summary rows
    # ------------------------------------------------------------------
    df_work = _clean_rows(df_work, warnings)

    # ------------------------------------------------------------------
    # 4. Build order list
    # ------------------------------------------------------------------
    orders: list[dict] = []
    for _, row in df_work.iterrows():
        area = str(row.get("AREA", "")).strip().upper()
        driver = str(row.get("DRIVER", "")).strip()
        truck = str(row.get("TRUCK", "")).strip()
        total_raw = row.get("TOTAL", 0)

        # Skip rows where TOTAL is 0 or not numeric
        try:
            total = int(float(total_raw))
        except (ValueError, TypeError):
            total = 0

        if total <= 0:
            continue
        if not area or area == "NAN":
            continue

        route_type = _classify_route(area)

        orders.append(
            {
                "dispatch_date": dispatch_date.isoformat(),
                "route_name": area,
                "route_type": route_type,
                "driver_name": driver if driver.lower() not in ("nan", "") else "TBA",
                "truck_registration": truck if truck.lower() not in ("nan", "") else "TBA",
                "target_qty": total,
                "loaded_qty": 0,
                "status": STATUS_IN_QUEUE,
            }
        )

    logger.info("parse_order_sheet: extracted %d orders from '%s'", len(orders), sheet_name)
    return orders, warnings


def parse_all_sheets(
    file_obj: Union[bytes, io.BytesIO],
    dispatch_date: date,
) -> tuple[list[dict], list[str]]:
    """
    Parse both 'Orders' and 'Confect Orders' sheets and merge.
    Route names from the Confect sheet are prefixed with 'CONFECT — '
    to distinguish them.
    """
    if isinstance(file_obj, bytes):
        file_obj = io.BytesIO(file_obj)

    all_orders: list[dict] = []
    all_warnings: list[str] = []

    # Bread orders
    bread, warn = parse_order_sheet(io.BytesIO(file_obj.getvalue()), dispatch_date, "Orders")
    all_orders.extend(bread)
    all_warnings.extend(warn)

    return all_orders, all_warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_header_row(df: pd.DataFrame) -> int | None:
    """Scan rows looking for one containing both 'AREA' and 'TOTAL'."""
    for idx, row in df.iterrows():
        vals = [str(v).strip().upper() for v in row.values]
        if "AREA" in vals and "TOTAL" in vals:
            return int(idx)
    return None


def _build_column_map(cols: list[str]) -> dict[str, str]:
    """
    Return a dict mapping *original column name* → *canonical name*.
    Handles minor label variations found in the real workbook.
    """
    canonical_aliases: dict[str, list[str]] = {
        "AREA": ["AREA"],
        "SALESMAN": ["SALESMAN"],
        "DRIVER": ["DRIVER"],
        "TRUCK": ["TRUCK"],
        "SUPERIOR": ["SUPERIOR"],
        "BROWN": ["BROWN"],
        "WHOLE": ["WHOLE", "WHOLEWHEAT", "WHOLE WHEAT", "WHOLEGRAIN", "WHOLE GRAIN",
                   "SPAR WHOLE GRAIN", "SPAR WHOLEWHEAT"],
        "MR CHINGWA": ["MR CHINGWA"],
        "MRS CHINGWA": ["MRS CHINGWA"],
        "DR CHINGWA": ["DR CHINGWA"],
        "SPAR WHITE": ["SPAR WHITE"],
        "SPAR BROWN": ["SPAR BROWN"],
        "TOTAL": ["TOTAL"],
    }
    mapping: dict[str, str] = {}
    for orig in cols:
        cleaned = orig.strip().upper()
        for canonical, aliases in canonical_aliases.items():
            if cleaned in [a.upper() for a in aliases]:
                mapping[orig] = canonical
                break
        else:
            mapping[orig] = orig  # keep as-is
    return mapping


def _extract_working_df(df: pd.DataFrame, col_map: dict[str, str]) -> pd.DataFrame:
    """Rename columns using col_map and keep only the ones we care about."""
    df = df.rename(columns=col_map)
    keep = [c for c in ["AREA", "SALESMAN", "DRIVER", "TRUCK", "TOTAL"] if c in df.columns]
    return df[keep].copy()


def _clean_rows(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """
    Drop:
      - Rows where AREA is NaN / blank
      - Summary rows matching SUMMARY_ROW_KEYWORDS
      - Rows where AREA value starts with a numeric (subtotal rows)
    """
    if "AREA" not in df.columns:
        warnings.append("'AREA' column not found; cannot clean rows.")
        return df

    df = df.dropna(subset=["AREA"])
    df = df[df["AREA"].astype(str).str.strip() != ""]
    df = df[~df["AREA"].astype(str).str.strip().str.match(r"^\d")]

    def _is_summary(val: str) -> bool:
        v = val.strip().upper()
        for kw in SUMMARY_ROW_KEYWORDS:
            if v == kw.upper():
                return True
            # Also catch "TOTAL AREA 1 HARARE" etc.
            if kw.upper() in v and any(
                word in v for word in ("TOTAL", "GRAND", "DEPOTS AREA", "AREA 2")
            ):
                return True
        return False

    df = df[~df["AREA"].astype(str).map(_is_summary)]
    return df.reset_index(drop=True)


def _classify_route(route_name: str) -> str:
    """Return 'Freighter' if route_name is in FREIGHTERS list, else 'Local'."""
    return "Freighter" if route_name.upper() in [f.upper() for f in FREIGHTERS] else "Local"
