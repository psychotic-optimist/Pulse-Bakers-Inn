# Baker's Inn Dispatch Control Tower
## System Documentation

**Version:** 1.0  
**Prepared by:** Pulse Ltd  
**Client:** Baker's Inn (Superlinx Logistics)  
**Department:** Dispatch & Logistics  
**Date:** June 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Module Reference](#3-module-reference)
4. [Database Schema](#4-database-schema)
5. [User Roles & Access Control](#5-user-roles--access-control)
6. [Core Features](#6-core-features)
7. [TV Display Mode](#7-tv-display-mode)
8. [Depot Loading Plan](#8-depot-loading-plan)
9. [Import Pipeline](#9-import-pipeline)
10. [Calculations Engine](#10-calculations-engine)
11. [Configuration Reference](#11-configuration-reference)
12. [Deployment & Operations](#12-deployment--operations)
13. [Domain Glossary](#13-domain-glossary)

---

## 1. System Overview

The **Baker's Inn Dispatch Control Tower** is a real-time web application that manages the daily bread and confectionary dispatch operation at Baker's Inn. It provides visibility across warehouse loading, freighter depot runs, and local route deliveries — from the moment an order sheet is uploaded in the morning to the point trucks depart.

### Business Context

Baker's Inn produces bread (Superior, Brown, Whole Grain, and branded variants) and confectionary daily. Every morning, an Excel order sheet is generated listing quantities per route and truck. The Dispatch Control Tower ingests this sheet, tracks loading progress truck-by-truck, calculates estimated completion times, and projects live data onto a warehouse TV display visible to the loading crew.

### Key Capabilities

| Capability | Description |
|---|---|
| Order Import | Parse daily Excel order sheet and load into Supabase |
| Live Board | Airport-style departure board showing all trucks and loading status |
| Loading Progress | Per-truck loaded qty tracking with auto-derived status |
| ETC Calculation | Estimated time of completion per truck and per route |
| Depot Breakdown | SKU-level loading manifest per depot with per-truck quantities |
| TV Slideshow | Auto-rotating full-screen display for the warehouse wall TV |
| Session Tracker | Sequential freighter/local loading session timer with rate estimates |
| Analytics | Plotly charts — demand by route, progress, status distribution |
| Audit Trail | Full history of all changes with user attribution |
| User Management | Role-based access (viewer / supervisor / admin) |

---

## 2. Architecture

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend / UI | Streamlit (Python) |
| Database | Supabase (PostgreSQL) |
| ORM / Client | supabase-py v2.x |
| Data Processing | Pandas, openpyxl |
| Charts | Plotly Express / Graph Objects |
| Auth | Custom session-based (Supabase `users` table + bcrypt) |
| Auto-refresh | streamlit-autorefresh |
| Timezone | Africa/Harare (configurable via `DISPLAY_TIMEZONE`) |

### File Structure

```
project/
├── streamlit_app.py        # Main entry point — all UI rendering
├── config.py               # Constants, status strings, column definitions
├── dispatch_auth.py        # Authentication, session, role helpers
├── database.py             # Supabase queries for dispatch_orders, settings, users, audit
├── depot_database.py       # Supabase queries for depot_orders table
├── calculations.py         # ETC, progress, KPI, status derivation logic
├── importer.py             # Excel order sheet parser (parse_all_sheets)
└── requirements.txt        # Python dependencies
```

### Data Flow

```
Excel Order Sheet (.xlsx)
        │
        ▼
   importer.py
   parse_all_sheets()
        │
        ▼
   database.py
   bulk_insert_orders()
        │
        ▼
   Supabase: dispatch_orders
        │
        ├──► streamlit_app.py  (Dashboard board, KPI cards)
        ├──► calculations.py   (ETC, progress_pct, augment_orders)
        └──► TV Mode slideshow (depot SKU tables, local board)

Depot Entry Form (manual)
        │
        ▼
   depot_database.py
   upsert_depot_orders()
        │
        ▼
   Supabase: depot_orders
        │
        └──► TV slideshow slides 1…N (SKU breakdown per depot)
```

---

## 3. Module Reference

### `streamlit_app.py`

The single-file application entry point. Contains all Streamlit UI rendering functions.

| Function | Purpose |
|---|---|
| `main()` | App entry point — auth, routing, page rendering |
| `render_kpi_cards()` | 5-column KPI strip (stock, rate, demand, remaining, ETC) |
| `render_board_tab()` | HTML airport board table for one route type |
| `render_loading_plan()` | Freighter loading plan with per-route qty editing |
| `render_depot_entry_panel()` | Manual SKU-quantity grid for depot manifests |
| `render_supervisor_controls()` | Tabbed supervisor panel (session, update, create, settings) |
| `render_import_panel()` | Excel file uploader and confirm/clear controls |
| `render_charts()` | Plotly analytics tabs |
| `render_tv_mode()` | Full-screen TV slideshow (KPI → depots → local) |
| `_render_tv_kpi_cards()` | TV-specific KPI cards using depot loading rate for ETC |
| `_render_loading_session_tab()` | Sequential freighter/local session tracker |
| `_build_depot_sku_table()` | Generates the HTML SKU breakdown table for a depot |
| `_inject_css()` | Injects Baker's Inn branded CSS |
| `_render_pulse_footer()` | Pulse Ltd copyright footer |

**Constants defined in `streamlit_app.py`:**

| Constant | Value | Description |
|---|---|---|
| `DEPOT_LOADING_RATE` | `24_000` | Loaves per hour per truck at a freighter depot |
| `BREAD_SKUS_ORDER` | (list) | Display order for bread SKUs in depot tables |
| `CONFECT_SKUS_ORDER` | (list) | Display order for confectionary SKUs |
| `_KNOWN_DEPOTS` | (list) | Pre-populated depot name options |
| `_MAX_TRUCKS` | `6` | Max trucks supported per depot in manual entry form |

---

### `config.py`

Centralised constants shared across all modules.

| Constant | Description |
|---|---|
| `STATUS_IN_QUEUE` | `"In Queue"` — order not yet started |
| `STATUS_LOADING` | `"Loading"` — partially loaded |
| `STATUS_LOADED` | `"Loaded"` — fully loaded |
| `STATUS_AWAITING` | `"Awaiting Dispatch"` — loaded, not yet dispatched |
| `STATUS_DISPATCHED` | `"Dispatched"` — truck has left |
| `ALL_STATUSES` | Ordered list of all status strings |
| `MANUAL_OVERRIDE_STATUSES` | Statuses a supervisor can manually set |
| `BOARD_COLUMNS` | Column headers for the airport board table |
| `AUTOREFRESH_MS` | Auto-refresh interval in milliseconds (default 30,000) |
| `DISPLAY_TIMEZONE` | IANA timezone string (e.g. `"Africa/Harare"`) |
| `TV_DISPLAY_PARAM` | URL query param name to trigger TV mode (`"display"`) |

---

### `dispatch_auth.py`

Handles all authentication and role-based access.

| Function | Returns | Description |
|---|---|---|
| `require_auth()` | — | Shows login form if not authenticated; blocks app |
| `current_user()` | `str` | Username of logged-in user |
| `current_role()` | `str` | Role of logged-in user (`viewer`/`supervisor`/`admin`) |
| `is_admin()` | `bool` | True if role is `admin` |
| `can_edit()` | `bool` | True if role is `supervisor` or `admin` |
| `can_upload()` | `bool` | True if role is `supervisor` or `admin` |
| `logout()` | — | Clears session state |
| `hash_password()` | `str` | bcrypt hash of a plaintext password |

---

### `database.py`

All Supabase queries for the main operational tables.

| Function | Description |
|---|---|
| `get_orders_for_date(date)` | Fetch all dispatch orders for a given date |
| `bulk_insert_orders(orders)` | Insert list of order dicts; returns (inserted, errors) |
| `delete_orders_for_date(date, route_type?)` | Delete orders; optionally scoped to Local or Freighter |
| `update_loaded_qty(id, qty, user)` | Update loaded_qty; auto-derives status; writes audit |
| `update_status(id, status, user)` | Manual status override; writes audit |
| `create_single_order(order, user)` | Insert one order row |
| `get_order_by_id(id)` | Fetch a single order by primary key |
| `search_orders(date, query)` | Full-text search across route, truck, driver |
| `get_settings()` | Fetch production settings (bin level, hourly rate) |
| `update_settings(...)` | Save production settings |
| `get_history(limit)` | Fetch audit log rows |
| `list_users()` | Fetch all user accounts |
| `create_user(username, hashed_pw, role)` | Create a new user account |
| `_write_order_audit(...)` | Internal: write one audit record |

---

### `depot_database.py`

Supabase queries for the `depot_orders` table.

| Function | Description |
|---|---|
| `get_depot_orders(date)` | All depot_orders rows for a date |
| `get_depot_orders_by_depot(date, depot_name)` | Rows filtered to one depot |
| `get_depot_summary(date)` | Aggregated summary per depot: trucks, totals, rows |
| `upsert_depot_orders(rows)` | Bulk upsert depot order rows; returns (upserted, errors) |
| `delete_depot_orders_for_date(date, depot_name?)` | Delete depot rows; optionally scoped to one depot |

---

### `calculations.py`

Pure calculation logic — no Supabase calls, no Streamlit calls.

| Function | Description |
|---|---|
| `get_local_now()` | Current datetime in `DISPLAY_TIMEZONE` |
| `progress_pct(loaded, target)` | Percentage loaded; safe against divide-by-zero |
| `derive_status(loaded, target)` | Returns the correct status string from qty values |
| `augment_orders(orders, hourly_rate)` | Adds `progress_pct`, `remaining_qty`, `etc_display` to each order dict |
| `kpi_total_demand(orders)` | Sum of all target_qty values |
| `kpi_total_remaining(orders)` | Sum of all (target - loaded) values |
| `kpi_overall_progress(orders)` | Overall % loaded across all orders |
| `kpi_estimated_finish(orders, rate, buffer)` | Production-rate-based finish datetime |
| `format_etc(dt)` | Format a datetime as `HH:MM` string |

---

### `importer.py`

Parses the daily Excel order sheet.

| Function | Description |
|---|---|
| `parse_all_sheets(file_bytes, dispatch_date)` | Main entry point: parses all sheets, returns (orders, warnings) |

**Parsing logic:**
- Reads both `Orders` and `Confect Orders` sheets (if present)
- Identifies header rows dynamically
- Validates route names using Zimbabwean naming conventions
- Returns a list of dicts ready for `bulk_insert_orders()`
- Warnings list contains non-fatal issues (skipped rows, unrecognised names)

---

## 4. Database Schema

### `dispatch_orders`

The primary operational table — one row per truck per day.

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` | Primary key |
| `dispatch_date` | `date` | The date this order is for |
| `route_name` | `text` | Route label (e.g. `MUTARE 5`, `HATCLIFF 1`) |
| `route_type` | `text` | `Freighter` or `Local` |
| `driver_name` | `text` | Driver's full name |
| `truck_registration` | `text` | Truck plate (e.g. `AEW 9912`) |
| `target_qty` | `integer` | Ordered/planned bread quantity (loaves) |
| `loaded_qty` | `integer` | Actual quantity loaded so far |
| `status` | `text` | One of the five status strings |
| `created_at` | `timestamptz` | Row creation timestamp |
| `updated_at` | `timestamptz` | Last update timestamp |

**Conflict key:** `(dispatch_date, route_name, truck_registration)`

---

### `depot_orders`

Stores the SKU-level loading manifest for freighter depot trucks.

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` | Primary key |
| `dispatch_date` | `date` | The date this manifest is for |
| `depot_name` | `text` | Depot name (e.g. `HATCLIFF`, `MUTARE`) |
| `truck_label` | `text` | Sub-route label within the depot (e.g. `HATCLIFF 1`) |
| `truck_registration` | `text` | Truck plate |
| `sku_name` | `text` | Product name (e.g. `SUPERIOR`, `BROWN`) |
| `sku_group` | `text` | `bread` or `confect` |
| `ordered_qty` | `integer` | Quantity of this SKU to load onto this truck |
| `loaded_qty` | `integer` | Quantity actually loaded (updated as loading progresses) |
| `status` | `text` | Loading status for this SKU/truck |
| `created_at` | `timestamptz` | Row creation timestamp |

**Important:** `depot_orders` rows represent a *loading manifest* — what goes on the truck — not a customer order. The `ordered_qty` is what the depot requested; it is tracked against `loaded_qty` to compute ETC.

---

### `dispatch_order_history` (Audit)

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` | Primary key |
| `dispatch_order_id` | `uuid` | FK to `dispatch_orders` |
| `action` | `text` | Action type (e.g. `loaded_qty_updated`, `status_override`) |
| `old_value` | `text` | Previous value |
| `new_value` | `text` | New value |
| `changed_by` | `text` | Username who made the change |
| `created_at` | `timestamptz` | Timestamp of the change |

---

### `users`

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` | Primary key |
| `username` | `text` | Unique login name |
| `hashed_password` | `text` | bcrypt hash |
| `role` | `text` | `viewer`, `supervisor`, or `admin` |
| `created_at` | `timestamptz` | Account creation timestamp |

---

### `settings`

Single-row configuration table.

| Column | Type | Description |
|---|---|---|
| `id` | `integer` | Always `1` (singleton row) |
| `current_bin_level` | `integer` | Opening stock — loaves in the production bin at shift start |
| `hourly_production_rate` | `integer` | Bakery output in loaves per hour |
| `updated_at` | `timestamptz` | Last settings change |
| `changed_by` | `text` | Username who last changed settings |

---

## 5. User Roles & Access Control

| Feature | Viewer | Supervisor | Admin |
|---|:---:|:---:|:---:|
| View dashboard board | ✅ | ✅ | ✅ |
| View TV mode | ✅ | ✅ | ✅ |
| View depot breakdown | ✅ | ✅ | ✅ |
| Search orders | ✅ | ✅ | ✅ |
| Upload order sheet | ❌ | ✅ | ✅ |
| Update loaded qty | ❌ | ✅ | ✅ |
| Override status | ❌ | ✅ | ✅ |
| Create new order | ❌ | ✅ | ✅ |
| Enter depot quantities | ❌ | ✅ | ✅ |
| Edit production settings | ❌ | ✅ | ✅ |
| View audit trail | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |

---

## 6. Core Features

### 6.1 Order Import

A supervisor uploads the daily Excel workbook via the **Import Daily Order Sheet** panel. The `parse_all_sheets()` function reads both `Orders` and `Confect Orders` sheets. After parsing, a preview table is shown with totals before the supervisor clicks **Confirm Import**.

On confirm:
1. All existing **Local** orders for the date are deleted (freighter orders are preserved — they are managed separately via the Depot Loading Plan).
2. Parsed orders are bulk-inserted into `dispatch_orders`.

### 6.2 Dispatch Board

The board renders as an HTML table styled to look like an airport departure board. Two tabs: **Freighters** and **Local Routes**.

Columns: Route | Truck | Driver | Target Qty | Loaded Qty | Remaining | Progress | Status | ETC

Status is auto-derived:
- `loaded_qty == 0` → **In Queue**
- `0 < loaded_qty < target_qty` → **Loading**
- `loaded_qty >= target_qty` → **Loaded**

ETC is calculated in `calculations.augment_orders()` using the production hourly rate and remaining quantity.

### 6.3 Supervisor Update Controls

The **Update Order** tab lets a supervisor:
- Adjust the **loaded qty** for any order
- Apply a **manual status override** (e.g. force `Awaiting Dispatch` or `Dispatched`)

All changes are written to `dispatch_order_history`.

### 6.4 Loading Session Tracker

The **Loading Session** tab provides a two-phase sequential timer:
1. **Freighters Session** — starts when freighter loading begins
2. **Local Routes Session** — starts when local loading begins

Each session tracks:
- Elapsed time since start
- Trucks done (manually updated by supervisor)
- Throughput rate (trucks/hour, derived from elapsed + done)
- Remaining trucks
- Estimated finish time

Session state persists in `st.session_state` and survives auto-refresh. Both sessions also display a live summary strip at the top of the tab.

### 6.5 Production Settings

The **Production Settings** tab (supervisor/admin) sets two values stored in the `settings` table:

| Setting | Purpose |
|---|---|
| Opening Stock | Loaves already in the bin at shift start — used to offset initial demand |
| Hourly Production Rate | Bakery output (loaves/hour) — used to estimate when demand will be met |

---

## 7. TV Display Mode

Activate by appending `?display=true` to the application URL.

The TV mode renders a full-screen auto-rotating slideshow with no sidebar, no navigation, and a compact header. It auto-refreshes every 30 seconds via `st_autorefresh`.

### Slide Rotation

Slides advance every **15 seconds** based on the current Unix timestamp modulo the total slide count.

| Slide | Content | Shown when |
|---|---|---|
| 0 | KPI Overview | Always |
| 1 … N | Per-depot SKU breakdown | One per depot with saved data |
| Last | Local Routes board | Only when local orders exist |

> **Note:** If there are no local orders for the day, the Local Routes slide is omitted entirely. The slideshow cycles only through KPI + depot slides.

### TV KPI Cards

The TV KPI overview uses depot-aware finish estimation:

1. For each depot, for each truck: `remaining_qty ÷ DEPOT_LOADING_RATE` → truck ETC
2. Route ETC = slowest truck at that depot
3. Overall ETC = max across all depots

This reflects the real-world 12+ hour loading window for freighter depots, rather than the bakery production rate which would give an unrealistically short estimate.

| Card | TV Label | Source |
|---|---|---|
| Opening Stock | Opening Stock | `settings.current_bin_level` |
| Loading Rate | Loading Rate | `DEPOT_LOADING_RATE` (24k loaves/hr/truck) |
| Total Manifest | Total Manifest | Sum of all `target_qty` |
| Remaining | Remaining | Sum of remaining per order |
| Est. Finish | Est. Finish | Max depot ETC across all trucks |

### Per-Depot Slides

Each depot slide shows:
- A header banner: `► LOADING BREAKDOWN — {DEPOT NAME}`
- An HTML SKU table: bread SKUs (fixed order) → TOTAL BREAD row → confect SKUs
- A progress bar with loaves loaded / loaves ordered
- An ETC banner showing per-truck and overall "Done by HH:MM"

Zero-quantity confect rows are hidden on TV to maximise screen use.

---

## 8. Depot Loading Plan

Accessible from the **Depot Loading Plan** nav item.

### Purpose

Freighter trucks run to regional depots (Hatcliff, Mutare, Chinhoyi, etc.) and carry a specific SKU breakdown — not just a total bread quantity. The Depot Loading Plan captures this breakdown at the SKU level.

### Entry Form

A supervisor selects a depot and defines 1–6 trucks with labels (e.g. `HATCLIFF 1`, `HATCLIFF 2`) and registrations. They then fill a grid of quantities for every bread and confect SKU.

On **Save**:
1. Existing rows for that depot and date are deleted
2. New rows are upserted into `depot_orders`

Each row in `depot_orders` represents one (truck × SKU) combination.

### Saved Breakdown View

Below the entry form, all saved depots for the selected date are shown in expandable sections, each rendering the full SKU table with a progress bar.

### Loading Rate

Depot loading uses a fixed rate of **24,000 loaves per hour per truck**. Trucks at the same depot load simultaneously (in parallel), so the depot's ETC is determined by the **slowest truck** (max individual ETC).

---

## 9. Import Pipeline

### Supported Format

The Excel workbook must contain:
- An `Orders` sheet — bread orders by route and truck
- Optionally a `Confect Orders` sheet — confectionary quantities

### Parsing Steps (`importer.py → parse_all_sheets`)

1. Load workbook bytes with openpyxl (streaming mode for large files)
2. Detect header row by scanning for known column names
3. Iterate rows; skip blanks, subtotals, and header repeats
4. Validate route names against Zimbabwean naming patterns
5. Validate driver names (length, character set)
6. Construct order dicts with defaults (`loaded_qty=0`, `status="In Queue"`)
7. Return `(orders: list[dict], warnings: list[str])`

### Import Rules

- Only **Local** orders are deleted before re-import. Freighter orders entered manually in the Depot Loading Plan are never overwritten by an Excel import.
- Duplicate routes within a sheet produce a warning; the last occurrence wins.
- Rows with zero target qty are skipped.

---

## 10. Calculations Engine

All logic lives in `calculations.py` with no side effects.

### Status Derivation

```
loaded_qty == 0              → In Queue
0 < loaded_qty < target_qty  → Loading
loaded_qty >= target_qty     → Loaded
```

Manual overrides (`Awaiting Dispatch`, `Dispatched`) are set explicitly by supervisors and are not overwritten by the auto-derive logic unless loaded qty is subsequently changed.

### ETC (Estimated Time of Completion)

**Per-order ETC** (used on the dashboard board):
```
remaining = target_qty - loaded_qty
hours_needed = remaining / hourly_production_rate
ETC = now + hours_needed
```

**Depot truck ETC** (used on TV slides and the depot breakdown):
```
remaining = sum(ordered_qty - loaded_qty) for all SKUs on this truck
hours_needed = remaining / DEPOT_LOADING_RATE   # 24,000 loaves/hr
ETC = now + hours_needed
```

**Route/depot ETC:**
```
ETC = max(truck ETCs for all trucks at this depot)
```

### Progress Percentage

```
progress_pct = (loaded_qty / target_qty) × 100
              (returns 0 if target_qty == 0)
```

### Overall KPI Finish (dashboard)

```
total_remaining = Σ (target_qty - loaded_qty) for all orders
hours_needed = (total_remaining - buffer) / hourly_production_rate
ETC = now + hours_needed
```

`buffer` is the `current_bin_level` setting — loaves already available before the current production rate kicks in.

---

## 11. Configuration Reference

### Environment Variables

Set these in the Streamlit secrets file (`.streamlit/secrets.toml`) or as environment variables.

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon or service role key |

### `config.py` Constants

| Constant | Default | Notes |
|---|---|---|
| `AUTOREFRESH_MS` | `30000` | 30-second auto-refresh |
| `DISPLAY_TIMEZONE` | `"Africa/Harare"` | Used for all ETC display and session times |
| `TV_DISPLAY_PARAM` | `"display"` | URL param to activate TV mode |
| `BOARD_COLUMNS` | (list) | Column headers for the board table |

### `streamlit_app.py` Constants

| Constant | Default | Notes |
|---|---|---|
| `DEPOT_LOADING_RATE` | `24_000` | Loaves/hr/truck — adjust if the physical rate changes |
| `_MAX_TRUCKS` | `6` | Maximum trucks in the manual depot entry form |
| `SLIDE_SECONDS` | `15` | TV slideshow advance interval (set inside `render_tv_mode`) |

---

## 12. Deployment & Operations

### Running the Application

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### TV Mode

Append `?display=true` to the running URL and open on any browser connected to the warehouse display:

```
http://localhost:8501/?display=true
```

The page auto-refreshes every 30 seconds and requires no user interaction.

### Daily Workflow

| Time | Action | Who |
|---|---|---|
| Pre-shift | Upload Excel order sheet | Supervisor |
| Pre-shift | Enter depot SKU breakdown | Supervisor |
| Pre-shift | Set opening stock & production rate | Supervisor |
| Loading start | Start Freighters Session | Supervisor |
| During loading | Update trucks done count | Supervisor |
| During loading | Update loaded qty per route (if needed) | Supervisor |
| Freighters done | Mark Freighters Session complete | Supervisor |
| Local start | Start Local Routes Session | Supervisor |
| End of shift | Mark all remaining trucks loaded/dispatched | Supervisor |

### Auto-Refresh

The board refreshes every 30 seconds. All supervisors on different machines will see updates within one refresh cycle. No manual page reload is needed.

### Data Retention

Orders are date-scoped. Old dates are never automatically deleted — historical data is preserved for reporting and auditing. Use the "Clear Today's Orders" button only if a full reimport is needed for the current date.

---

## 13. Domain Glossary

| Term | Definition |
|---|---|
| **Freighter** | A long-haul truck that runs to a regional depot (Hatcliff, Mutare, Chinhoyi, etc.) |
| **Local** | A truck that distributes to retail customers within the Harare area |
| **Depot** | A regional distribution point that Freighter trucks service |
| **Route** | A named truck run (e.g. `MUTARE 5`, `HATCLIFF 1`) |
| **SKU** | Stock Keeping Unit — a specific product variant (e.g. `SUPERIOR`, `BROWN`, `MEGA CREAM BUN`) |
| **Loading Manifest** | The per-SKU quantity breakdown assigned to a specific truck for a specific depot run |
| **Opening Stock** | The quantity of loaves already available in the production bin at shift start |
| **ETC** | Estimated Time of Completion — when a truck or depot is expected to finish loading |
| **DEPOT_LOADING_RATE** | The fixed loading throughput: 24,000 loaves per hour per truck |
| **In Queue** | Status: truck assigned, loading not yet started |
| **Loading** | Status: truck partially loaded |
| **Loaded** | Status: truck fully loaded to target quantity |
| **Awaiting Dispatch** | Status: truck loaded and ready but not yet departed |
| **Dispatched** | Status: truck has left the premises |
| **Supervisor** | A role with write access — can update quantities, override statuses, enter depot data |
| **Admin** | A role with full access including audit trail and user management |
| **TV Mode** | A URL-activated full-screen display mode intended for the warehouse wall TV |
| **Session Tracker** | A timer tool that estimates loading completion based on throughput rate |

---

*Documentation generated by Pulse Ltd · Baker's Inn Dispatch Control Tower v1.0*  
*© 2026 Baker's Inn. All rights reserved.*
