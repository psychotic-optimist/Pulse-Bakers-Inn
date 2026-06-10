"""
depot_importer.py — Excel parser for Baker's Inn depot pre-alert order sheets.

Each depot sheet has two sections:
  Section 1 — Depot totals (rows 1–~27): single PRODUCT / QUANTITY column pair.
  Section 2 — Loading breakdown (after '▸  LOADING BREAKDOWN - <DEPOT>' row):
              column headers = truck sub-routes (HATCLIFF 1, HATCLIFF 2 …),
              with interleaved blank (merged) columns.

Public API
----------
parse_depot_excel(file_obj, dispatch_date) -> (list[dict], list[str])
    Returns flat rows ready for depot_database.upsert_depot_orders + warnings.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from typing import Union

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEPOT_SHEETS_SKIP: set[str] = {"Sheet1", "PARAMETERS"}

BREAD_SKUS: set[str] = {
    "SUPERIOR",
    "BROWN",
    "WHOLE GRAIN",
    "WHOLE WHEAT",
    "WHOLEGRAIN",
    "WHOLEWHEAT",
    "SPAR WHITE",
    "SPAR BROWN",
    "SPAR WHOLE GRAIN",
    "SPAR WHOLEWHEAT",
}

# Prefixes that mark subtotal / grand-total rows to skip
SKIP_SKU_PREFIXES: tuple[str, ...] = (
    "TOTAL",
    "GRAND TOTAL",
    "SUPERVISOR",
    "HEADLOADER",
    "PRODUCT DESCRIPTION",
    "TIME & BAY",
    "TRUCK REG",
    "ROUTE",
    "DEPOT ORDER",
)

# Rows whose labels are structural (not SKUs) that we always skip
STRUCTURAL_LABELS: set[str] = {
    "TOTAL BI",
    "TOTAL MR C",
    "TOTAL SPAR",
    "TOTAL BREAD",
    "GRAND TOTAL: INITIAL ORDER",
}

STATUS_IN_QUEUE = "In Queue"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_depot_excel(
    file_obj: Union[bytes, io.BytesIO],
    dispatch_date: date,
) -> tuple[list[dict], list[str]]:
    """
    Parse all depot sheets in *file_obj* and return:
      - flat list of row dicts matching the depot_orders schema
      - list of warning strings for non-fatal issues
    """
    if isinstance(file_obj, bytes):
        file_obj = io.BytesIO(file_obj)
    else:
        file_obj.seek(0)

    warnings: list[str] = []
    all_rows: list[dict] = []

    try:
        wb = load_workbook(file_obj, read_only=True, data_only=True)
    except Exception as exc:
        msg = f"Failed to open workbook: {exc}"
        logger.error(msg)
        return [], [msg]

    depot_sheets = [s for s in wb.sheetnames if s not in DEPOT_SHEETS_SKIP]
    if not depot_sheets:
        warnings.append("No depot sheets found (all sheets are in the skip list).")
        return [], warnings

    for sheet_name in depot_sheets:
        try:
            ws = wb[sheet_name]
            rows, warns = _parse_sheet(ws, sheet_name, dispatch_date)
            all_rows.extend(rows)
            warnings.extend(warns)
        except Exception as exc:
            msg = f"Error parsing sheet '{sheet_name}': {exc}"
            logger.error(msg)
            warnings.append(msg)

    logger.info(
        "parse_depot_excel: extracted %d rows from %d depot sheet(s)",
        len(all_rows),
        len(depot_sheets),
    )
    return all_rows, warnings


# ---------------------------------------------------------------------------
# Sheet-level parser
# ---------------------------------------------------------------------------

def _parse_sheet(
    ws,
    sheet_name: str,
    dispatch_date: date,
) -> tuple[list[dict], list[str]]:
    """Parse one depot worksheet; return (rows, warnings)."""
    warnings: list[str] = []
    depot_name = sheet_name.strip().upper()

    # Materialise all rows (openpyxl read_only mode)
    raw_rows: list[tuple] = list(ws.iter_rows(values_only=True))
    if not raw_rows:
        warnings.append(f"Sheet '{sheet_name}' is empty.")
        return [], warnings

    # ── Locate the LOADING BREAKDOWN divider row ──────────────────────
    breakdown_row_idx = _find_breakdown_row(raw_rows)
    if breakdown_row_idx is None:
        warnings.append(
            f"Sheet '{sheet_name}': '▸  LOADING BREAKDOWN' divider not found. "
            "Skipping loading breakdown section."
        )
        return [], warnings

    breakdown_rows = raw_rows[breakdown_row_idx + 1 :]  # rows after the divider

    # ── Parse truck sub-route header (first row after divider) ────────
    if not breakdown_rows:
        warnings.append(f"Sheet '{sheet_name}': no rows after LOADING BREAKDOWN divider.")
        return [], warnings

    header_row = breakdown_rows[0]
    truck_cols = _parse_truck_columns(header_row, depot_name)

    if not truck_cols:
        warnings.append(
            f"Sheet '{sheet_name}': could not identify truck sub-route columns in header row."
        )
        return [], warnings

    # ── Parse TRUCK REG row (second row after divider, if present) ────
    truck_reg_map: dict[int, str] = {}
    if len(breakdown_rows) > 1:
        reg_row = breakdown_rows[1]
        label = str(reg_row[0] or "").strip().upper()
        if "TRUCK REG" in label:
            for col_idx, truck_label in truck_cols.items():
                val = reg_row[col_idx] if col_idx < len(reg_row) else None
                if val and str(val).strip().upper() not in ("NONE", ""):
                    truck_reg_map[col_idx] = str(val).strip()
            breakdown_rows = breakdown_rows[2:]  # skip header + reg rows
        else:
            breakdown_rows = breakdown_rows[1:]  # skip header only
    else:
        breakdown_rows = []

    # Skip TIME & BAY row if present
    if breakdown_rows:
        first_label = str(breakdown_rows[0][0] or "").strip().upper()
        if "TIME" in first_label and "BAY" in first_label:
            breakdown_rows = breakdown_rows[1:]

    # ── Parse SKU rows ────────────────────────────────────────────────
    rows: list[dict] = []
    for raw_row in breakdown_rows:
        if not raw_row or raw_row[0] is None:
            continue

        sku_raw = str(raw_row[0]).strip()
        if not sku_raw:
            continue

        # Skip structural / total / metadata rows
        if _should_skip_row(sku_raw):
            continue

        sku_name = _normalise_sku(sku_raw)
        sku_group = classify_sku_group(sku_raw)

        for col_idx, truck_label in truck_cols.items():
            val = raw_row[col_idx] if col_idx < len(raw_row) else None
            qty = _safe_int(val)
            if qty is None or qty < 0:
                qty = 0

            rows.append(
                {
                    "dispatch_date": dispatch_date.isoformat(),
                    "depot_name": depot_name,
                    "truck_label": truck_label,
                    "truck_registration": truck_reg_map.get(col_idx),
                    "sku_group": sku_group,
                    "sku_name": sku_name,
                    "ordered_qty": qty,
                    "loaded_qty": 0,
                    "status": STATUS_IN_QUEUE,
                }
            )

    if not rows:
        warnings.append(
            f"Sheet '{sheet_name}': no SKU rows extracted from loading breakdown."
        )

    return rows, warnings


# ---------------------------------------------------------------------------
# Column / header helpers
# ---------------------------------------------------------------------------

def _find_breakdown_row(raw_rows: list[tuple]) -> int | None:
    """Return the row index containing the LOADING BREAKDOWN divider, or None."""
    for idx, row in enumerate(raw_rows):
        for cell in row:
            if cell is None:
                continue
            val = str(cell).strip()
            if "LOADING BREAKDOWN" in val.upper():
                return idx
    return None


def _parse_truck_columns(header_row: tuple, depot_name: str) -> dict[int, str]:
    """
    Given the header row directly after the LOADING BREAKDOWN divider,
    return a mapping of {column_index: truck_label}.

    Column layout: col 0 = product description, col 1 = Truck1,
    col 2 = blank (merged), col 3 = Truck2, col 4 = blank, …
    i.e. truck data is in odd columns (1, 3, 5, …) and every other
    column is blank/merged.  But we detect by scanning for non-blank,
    non-"PRODUCT" values.
    """
    truck_cols: dict[int, str] = {}
    for col_idx, cell in enumerate(header_row):
        if col_idx == 0:
            continue  # always the product-description column
        if cell is None:
            continue
        val = str(cell).strip()
        if not val or val.upper() == "PRODUCT DESCRIPTION":
            continue
        # Accept any label that looks like a depot sub-route label
        # e.g. "HATCLIFF 1", "Bindura 2", "MT DARWIN"
        upper_val = val.upper()
        # Must contain the depot name or be a standalone name (single-truck depots)
        depot_base = depot_name.split()[0]  # e.g. "HATCLIFF" from "HATCLIFF"
        if depot_base in upper_val or re.search(r"\d", val):
            truck_cols[col_idx] = val.strip().upper()
        elif not truck_cols:
            # First non-blank, non-desc column — accept it (single-truck depots)
            truck_cols[col_idx] = val.strip().upper()

    return truck_cols


# ---------------------------------------------------------------------------
# SKU helpers
# ---------------------------------------------------------------------------

def classify_sku_group(sku_raw: str) -> str:
    """Return 'bread' if *sku_raw* is a bread SKU, else 'confect'."""
    normalised = sku_raw.strip().upper()
    # Exact match first
    if normalised in BREAD_SKUS:
        return "bread"
    # Partial match for slight variations (e.g. "WHOLE WHEAT GRAIN")
    for bread in BREAD_SKUS:
        if bread in normalised or normalised in bread:
            return "bread"
    return "confect"


def _normalise_sku(sku_raw: str) -> str:
    """Trim and title-case the SKU name for consistent display."""
    return sku_raw.strip().title()


def _should_skip_row(label: str) -> bool:
    """Return True if this row label is a total/structural row we should skip."""
    upper = label.strip().upper()
    # Check exact structural labels
    if upper in {s.upper() for s in STRUCTURAL_LABELS}:
        return True
    # Check prefixes
    for prefix in SKIP_SKU_PREFIXES:
        if upper.startswith(prefix.upper()):
            return True
    return False


def _safe_int(val) -> int | None:
    """Convert a cell value to int, returning None if it cannot be parsed."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    # Might be a formula string or text like "30 Boxes"
    s = str(val).strip()
    if not s or s.upper() in ("NONE", "N/A", "-", "—"):
        return None
    # Extract leading number from strings like "30 Boxes"
    m = re.match(r"^(\d+)", s)
    if m:
        return int(m.group(1))
    return None
