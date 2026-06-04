"""
config.py — Centralised configuration constants for Bakery Dispatch Control Tower.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Route classification
# ---------------------------------------------------------------------------
FREIGHTERS: list[str] = [
    "HATCLIFF",
    "HATCLIFF DEPOT 1",
    "HATCLIFF DEPOT 2",
    "HATCLIFF DEPOT 3",
    "HATCLIFF DEPOT 4",
    "HATCLIFF DEPOT 5",
    "MUTARE 1",
    "MUTARE 2",
    "MUTARE 3",
    "MUTARE 4",
    "MUREWA",
    "MUREWA 1",
    "MUREWA 2",
    "CHINHOYI 1",
    "CHINHOYI",
    "CHEGUTU",
    "CHEGUTU 2",
    "BINDURA",
    "BINDURA 2",
    "MT DARWIN",
    "MAPINI",
]

# ---------------------------------------------------------------------------
# Rows in the uploaded Excel that are summary / header / sub-total rows
# and must NOT be imported as individual dispatch orders.
# ---------------------------------------------------------------------------
SUMMARY_ROW_KEYWORDS: list[str] = [
    "BINDURA",
    "MAPINI",
    "CHINHOYI",
    "CHEGUTU",
    "DEPOTS AREA",
    "DZ NORTON",
    "TOTAL AREA",
    "GRAND TOTAL",
    "TOTAL DEPOTS",
    "TOTAL HARARE",
    "SOUTH WEST",
    "KUWADZANA",
    "CHITUNGWIZA",
    "MBARE/WATERFALLS",
    "JUDAH",
    "CECELIA",
    "TONGAI",
    "MELODY",
    "NORMAN",
    "RUMBIDZAI",
    "PAUL GOWANYIKA",
    "BRIAN PARADZA",
    "MR CHINGWA 1",
    "MR C HATCLIFFE",
    "CDB HATCLIFFE",
    "AREA 2",
    "BULAWAYO",
]

# ---------------------------------------------------------------------------
# Order statuses
# ---------------------------------------------------------------------------
STATUS_IN_QUEUE = "🔴 In Queue"
STATUS_LOADING = "🟢 Loading"
STATUS_LOADED = "🔵 Loaded"
STATUS_AWAITING = "🟡 Awaiting Production"
STATUS_DISPATCHED = "⚫ Dispatched"

ALL_STATUSES: list[str] = [
    STATUS_IN_QUEUE,
    STATUS_LOADING,
    STATUS_LOADED,
    STATUS_AWAITING,
    STATUS_DISPATCHED,
]

MANUAL_OVERRIDE_STATUSES: list[str] = [
    STATUS_AWAITING,
    STATUS_DISPATCHED,
]

# ---------------------------------------------------------------------------
# Auto-refresh interval (milliseconds)
# ---------------------------------------------------------------------------
AUTOREFRESH_MS: int = 30_000

# ---------------------------------------------------------------------------
# Session timeout (seconds of inactivity)
# ---------------------------------------------------------------------------
SESSION_TIMEOUT_SECONDS: int = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Timezone for display
# ---------------------------------------------------------------------------
DISPLAY_TIMEZONE: str = "Africa/Harare"

# ---------------------------------------------------------------------------
# TV display query param
# ---------------------------------------------------------------------------
TV_DISPLAY_PARAM: str = "display"

# ---------------------------------------------------------------------------
# Airport board columns
# ---------------------------------------------------------------------------
BOARD_COLUMNS: list[str] = [
    "Route",
    "Truck",
    "Driver",
    "Target Qty",
    "Loaded Qty",
    "Remaining Qty",
    "Progress %",
    "Status",
    "ETC",
]
