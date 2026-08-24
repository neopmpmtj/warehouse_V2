# CentCompras — Central Warehouse

A Django web application for a company with a **central warehouse** and **satellite branches**. Warehouse staff manage the catalogue, purchase orders, and goods receipt today. Branch staff will later browse the catalogue from a phone browser and place orders against central stock — including in areas with poor mobile coverage.

This repository is an early-stage MVP built incrementally: one concept per phase, with clear separation of responsibilities and no unnecessary frameworks.

---

## Project status

*Last updated: 24 August 2026, 11:20 WEST.*

**Phases 0–5 are done.** Item `internal_code` **Phases 1–2 are done.** **Sub-families catalogue slice is done.** **Warehouse FIFO stock reservation (D32) is done.** **Request threads (catalogue-gap requests) are done.** **Request-threads review M1–M5 and L1–L6 are done.** **Company Voice is built.** **Company Voice review H1, M1–M9, L1–L8 are done.** **Next:** Phase 6 — email automation. See [`docs/handoff.md`](docs/handoff.md).

> **Pick up here:** [`docs/handoff.md`](docs/handoff.md) — condensed state, locked decisions, and the exact next task. Sequencing: [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md).

### User roles (practice with these)

| User type | Example (after seed) | Can do today |
|-----------|----------------------|--------------|
| **Warehouse admin** | `warehouse.admin@centcompras.dev` | Full catalogue, POs (including approve any amount), goods receipts, stock adjust, `/manage/approval-limits/` (`warehouse_admins`). Cannot log into `/admin/`. |
| **Warehouse manager** | `warehouse.manager@centcompras.dev` (grade 1); also `manager2` / `manager3` | Grade 1: add/edit catalogue and POs (submit, no approve). Grade 2+: approve within caps. No delete / no stock adjust. |
| **Warehouse operator** | `warehouse.operator@centcompras.dev` (grade 1); also `operator2` | Grade 1: read-only. Grade 2: mutate closed circuit. Never approve. |
| **Branch users** | `branch.operator.north@…` / `branch.manager.north@…` / `branch.admin.north@…`, `branch.operator.south@…` / `branch.manager.south@…`, `branch.dual@…` | Branch picker, read-only catalogue (cost hidden, stock hint), requisição interna, and request threads (catalogue-gap requests). |
| **Django superuser** | from `createsuperuser` | Site admin at `/admin/` only. The only users who may use Django admin. |

After `./scripts/seed_dev_data.sh`, seeded users share password **`devpass123`**. The seed creates **branches** (North, South) and **branch users**, but does **not** create a superuser.

**Procurement:** admins approve any PO; managers grade 2+ approve within EUR gross caps (self vs others); operators never approve. Reject / short-shipment close / stock adjust require a reason. **Stock:** admins may `adjust_stock`; operator 2 and managers/admins record goods receipts.

### Recommended next session

1. Read [`docs/handoff.md`](docs/handoff.md).
2. Fresh environment: `python manage.py migrate`, `./scripts/seed_dev_data.sh`, and `createsuperuser` (the seed does not create one).
3. Practice: warehouse user → `/manage/items/`, `/manage/catalog/`, `/manage/purchase-orders/`, `/manage/goods-receipts/` (admins also `/manage/approval-limits/`).
4. **Next:** [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) §13 — **Phase 6: email automation** (wire notify stubs; templates EN + pt-PT).

---

## Business scenario

A central warehouse holds the master product catalogue and stock. Stock is a **movement ledger**: goods receipts write `StockMovement` rows and update cached `Item.quantity`. Quantity is never typed on the item form.

Satellite branches order against that stock via **Requisição interna** (Phase 5 — complete). PostgreSQL is the **source of truth**.

Warehouse staff work at `/manage/items/`, `/manage/catalog/`, `/manage/purchase-orders/`, `/manage/approval-limits/` (admins), and `/manage/goods-receipts/` via groups `warehouse_admins`, `warehouse_managers`, and `warehouse_data_operators`. Django admin is reserved for superusers.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django 6.1 |
| Database | PostgreSQL (`centcompras_db`) |
| Frontend | Plain HTML, plain JavaScript |
| Offline | (future — not implemented; previously removed) |
| Logging | `logging_utils` — console + rotating files in `logs/` |

No React, Vue, or similar frontend framework.

---

## What works today

### Authentication

- Custom `User` model (`accounts`) — email login, no username field; `warehouse_grade`; optional per-user timezone (default `Europe/Lisbon`)
- Session login/logout at `/accounts/login/` and `/accounts/logout/`
- Warehouse roles via Django groups
- Django admin (superuser only) for users and groups
- Consoles and APIs require login; APIs return 401 when unauthenticated

> **Branches + requisição + goods issue + branch receipt are built (Phase 5 complete).** `Branch` + `BranchMembership`, `ActiveBranchMiddleware`, `/branch/select/` picker, Django-admin CRUD, the read-only `/branch/catalog/` (cost hidden, stock hint), `/branch/requests/` (requisição through `approved`, manager caps), warehouse goods issue (`/manage/internal-requests/`, `/manage/branch-approval-limits/`), and branch receipt + branch stock (`/branch/receipts/`). Locked decisions (archived): [`docs/archive/phase5-brainstorm-260821-1530.md`](docs/archive/phase5-brainstorm-260821-1530.md).
>
> **Request threads are built.** `threads` app: a branch opens a written thread (subject + free text) when the needed item is **not in the catalogue**; warehouse engages; the item is created via the item console and linked to the thread; only the opener closes (branch manager/admin + warehouse admin may force-close). `/branch/threads/` (branch side) and `/manage/threads/` (all branches, filters, link-item, override close). Unread badges via `ThreadReadState`. Manual: [`08-request-threads.md`](docs/user-manuals/08-request-threads.md).

Production will use Google OAuth (not implemented in dev).

### Item catalogue

- `Item`: family, optional `internal_code`, `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active` (new items start inactive), three **manual** selling prices (`retail_price`, `wholesale_price`, `special_price`), cached `quantity` (ledger only).
- `SupplierItemPrice`: supplier × item → `cost_price` + `primary` (one primary per item). Dynamic cost source for purchase orders.
- Family and supplier names are case-insensitive unique. The console UI does not rename them.
- Audit: `ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog`, `SupplierItemPriceChangeLog`.
- All mutations through [`products/services.py`](products/services.py).
- CLI (dev/bootstrap): `python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16 --internal-code CEM-50 --internal-code CEM-50`

### Consoles

- `/` — staff dashboard
- `/manage/items/` — items, families, suppliers, selling prices, supplier prices
- `/manage/catalog/` — read-only manager catalog: stock, reorder level, selling + buying price, suppliers (cost visible to warehouse groups only)
- `/manage/purchase-orders/` — POs, lines, discounts, submit/approve (grades + EUR gross caps); a line is **rejected** if the supplier has no price for the item
- `/manage/approval-limits/` — PO approval caps (warehouse admins may edit)
- `/manage/goods-receipts/` — receipts (partial OK), stock movements, admin stock adjust
- `/manage/internal-requests/` — branch request queue + goods issue (partial OK, short-close)
- `/manage/threads/` — request threads (catalogue-gap requests: all branches, reply, link items, override close)
- `/manage/branch-approval-limits/` — branch manager caps (warehouse admins may edit)
- Supplier email on PO approval is a **stub** (Phase 6)

### URL layout

| Path | Purpose |
|------|---------|
| `/` | Staff dashboard (catalogue view permission) |
| `/manage/items/` | Warehouse item console |
| `/manage/catalog/` | Manager catalog (stock + price view, read-only) |
| `/manage/purchase-orders/` | Purchase-order console |
| `/manage/approval-limits/` | PO approval caps (EUR gross; warehouse admins may edit) |
| `/manage/goods-receipts/` | Goods receipt + stock console |
| `/manage/internal-requests/` | Request queue + goods issue console |
| `/manage/threads/` | Request threads console (catalogue-gap requests) |
| `/manage/branch-approval-limits/` | Branch manager caps (warehouse admins may edit) |
| `/api/manage/items/` | Item JSON API |
| `/api/manage/catalog/` | Manager catalog JSON API (joined stock + prices) |
| `/api/manage/families/` | Family JSON API |
| `/api/manage/suppliers/` | Supplier JSON API |
| `/api/manage/supplier-prices/` | Supplier price JSON API |
| `/api/manage/purchase-orders/` | Purchase-order JSON API (approve needs capability + grade) |
| `/api/manage/approval-limits/` | Approval-limit JSON API (PATCH is warehouse-admin only) |
| `/api/manage/goods-receipts/` | Goods receipt JSON API |
| `/api/manage/internal-requests/` | Request queue + goods issue JSON API |
| `/api/manage/threads/` | Request threads JSON API (list / messages / link / close) |
| `/api/manage/branch-approval-limits/` | Branch caps JSON API (PATCH is warehouse-admin only) |
| `/api/manage/purchase-orders/<id>/receipt-summary/` | Per-line ordered/received/remaining |
| `/api/manage/stock-movements/` | Stock movement ledger (`?item_id=` filter) |
| `/api/manage/stock-adjustments/` | Manual stock adjustment (POST; `can_adjust_stock`) |
| `/accounts/login/` | Email + password login |
| `/accounts/logout/` | Log out |
| `/branch/select/` | Branch picker (0 / 1 / N memberships) |
| `/branch/catalog/` | Branch catalog (read-only; cost hidden, stock hint) |
| `/api/branch/catalog/` | Branch catalog JSON API (cost hidden, stock hint) |
| `/branch/requests/` | Requisição interna (branch list + editor) |
| `/branch/threads/` | Request threads (catalogue-gap requests, branch side) |
| `/api/branch/requests/` | Requisição interna JSON API (draft → approved) |
| `/branch/receipts/` | Branch receipts (confirm dispatches, branch stock) |
| `/api/branch/receipts/` | Branch receipts JSON API (receive / short-close / adjust) |
| `/admin/` | Django admin (**superuser only**) |

There is no `GET /api/products/` and no `/service-worker.js`.

---

## Project structure

```text
warehouse/
├── manage.py
├── requirements.txt
├── config/                   # settings package (base/dev/prod/test) + urls.py
├── accounts/                 # custom User (email, timezone, warehouse_grade), login, groups, authz
├── branches/                 # tenancy: Branch + BranchMembership, picker, middleware
├── products/                 # catalogue + pricing
├── procurement/              # purchase orders
├── inventory/                # goods receipt + stock ledger
├── threads/                  # request threads (catalogue-gap requests)
├── logging_utils/            # console + logs/
├── docs/                     # handoff, plan, reviews, user manuals, tenancy design
├── scripts/                  # seed_dev_data.sh
├── AGENTS.md                 # agent instructions
└── .cursor/                  # Cursor rules
```

[`products/README.md`](products/README.md) is a **historical** catalogue build log.

---

## Setup

First-time setup from a fresh clone. Run all commands from the project root.

### 1. Virtual environment and dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL

The app expects a PostgreSQL database (local dev defaults: `centcompras_db`, user from `POSTGRES_USER`). Connection is configured via `DATABASE_URL` in `.env` (primary) or `POSTGRES_*` env vars (fallback). See [`config/settings/base.py`](config/settings/base.py).

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE centcompras_db;
ALTER USER postgres WITH PASSWORD 'your_password_here';
\q
```

### 3. Environment (`.env`)

Settings are split into a package: `config/settings/base.py` (shared), `dev.py` (local), `prod.py` (VPS), `test.py` (test runner). `manage.py test` auto-selects `config.settings.test`; local runs default to `config.settings.dev`; production sets `DJANGO_SETTINGS_MODULE=config.settings.prod`.

Secrets live in `.env` (gitignored). Copy the template and set the database connection:

```bash
cp .env.example .env
# edit DATABASE_URL (and optionally SECRET_KEY / DEBUG / ALLOWED_HOSTS)
```

`DATABASE_URL` is the primary DB setting (dev and prod); `POSTGRES_*` vars remain a fallback for local dev.

### 4. Google OAuth login (optional until configured)

Login-only Google Sign-In (scopes: openid, email, profile) — **no** Calendar/Drive/Gmail. Set in `.env`:

```ini
AUTH_MODE=both            # both = password + Google (dev + initial prod); google_only = Google only
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/accounts/google/callback/  # loopback for Desktop-app client
```

- Google login is **existing-only**: the email must already exist as a user (no auto-create).
- During dev, keep `AUTH_MODE=both`; to test the Google flow create one user whose email is a real Google account you control.
- At deploy: start `both`, flip to `google_only` only after every user has linked Google once.

### 5. Migrate and create site admin

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # prompts for email + password (not username)
```

`createsuperuser` creates a **site admin** for `/admin/`. That user cannot use the warehouse consoles until you add them to a warehouse group (or use a seeded warehouse user).

### 5. Seed test data

```bash
chmod +x scripts/seed_dev_data.sh   # first time only
./scripts/seed_dev_data.sh
```

This creates (idempotent):

| Item | Details |
|------|---------|
| **Warehouse users** | `warehouse.admin@…` / `warehouse.manager@…` / `manager2` / `manager3` / `warehouse.operator@…` / `operator2` (grades as seeded) |
| **Families, suppliers, items, supplier prices** | sample catalogue via `products/services.py` |
| **Password** | `devpass123` (override with `--password`) |

It also creates **branches** (North, South) and **branch users**. It does **not** create a Django superuser. Options: `--skip-items`, `--skip-warehouse`, `--skip-branches`.

Items can also be added in `/manage/items/` or:

```bash
python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16 --internal-code CEM-50
```

### 6. Test the application

1. Open `http://localhost:8000/` — redirected to login.
2. Log in as `warehouse.admin@centcompras.dev` / `devpass123`.
3. Open `/manage/items/`, `/manage/catalog/`, `/manage/purchase-orders/`, `/manage/goods-receipts/`.

Use **one hostname** consistently (`localhost` **or** `127.0.0.1`, not both).

### 7. Logging

Logs go to `logs/` (gitignored):

| File | Logger name |
|------|-------------|
| `logs/centcompras.log` | General |
| `logs/accounts.log` | `centcompras.accounts` |
| `logs/products.log` | `centcompras.products` |
| `logs/procurement.log` | `centcompras.procurement` |
| `logs/inventory.log` | `centcompras.inventory` |
| `logs/branches.log` | `centcompras.branches` |
| `logs/django.log` | `centcompras.django` (HTTP requests) |

```python
from logging_utils import get_logger

logger = get_logger("centcompras.products")
logger.info("Something happened")
```

Configuration: `logging_utils/logging_config.py`.

### Quick reference (daily dev)

```bash
source .venv/bin/activate
python manage.py runserver
```

First-time or reset DB: steps 1–4, then `./scripts/seed_dev_data.sh`.

Practice logins: `warehouse.admin@centcompras.dev`, `warehouse.manager@centcompras.dev` / `manager2` / `manager3`, `warehouse.operator@centcompras.dev` / `operator2` — password `devpass123`.

Tests:

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders threads
```

Migrations: `accounts/0001–0003`, `products/0001–0008`, `procurement/0001–0005`, `inventory/0001–0003`, `orders/0001–0002`, `threads/0001`. Run `migrate` after pull if schema changed.

---

## Architecture (current)

```text
PostgreSQL
    ↑
User, Item, FamilyProduct, Supplier, SupplierItemPrice,
PurchaseOrder(+lines), ApprovalLimit, GoodsReceipt(+lines), StockMovement
    ↑
services.py / permissions.py   (all mutations)
    ↑
views (login required) → API + HTML
    (item console, PO console, goods-receipt console)
```

---

## Further reading

- **Start here:** [`docs/handoff.md`](docs/handoff.md)
- [`docs/archive/phase5-roadmap-260821-1618.md`](docs/archive/phase5-roadmap-260821-1618.md) — Phase 5 roadmap (archived)
- [`docs/archive/phase5-brainstorm-260821-1530.md`](docs/archive/phase5-brainstorm-260821-1530.md) — locked decisions A1–B8 (archived)
- [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) — **living plan**: sequencing + status tracker + locked decisions (update every session)
- [`docs/archive/code-review-full-2026-08-21-1303.md`](docs/archive/code-review-full-2026-08-21-1303.md) — follow-up review (concluded, N1–N12 applied)
- [`docs/archive/code-review-full-2026-08-20-2208.md`](docs/archive/code-review-full-2026-08-20-2208.md) — prior full review (concluded)
- [`docs/archive/code-review-inventory-2026-08-20.md`](docs/archive/code-review-inventory-2026-08-20.md) — Phase 3 review (concluded)
- [`docs/archive/code-review-2026-08-20.md`](docs/archive/code-review-2026-08-20.md) · [`docs/archive/code-review-audit.md`](docs/archive/code-review-audit.md) — archived reviews
- [`docs/user-manuals/01-items.md`](docs/user-manuals/01-items.md) · [`docs/user-manuals/02-purchase-orders.md`](docs/user-manuals/02-purchase-orders.md) · [`docs/user-manuals/03-goods-receipts.md`](docs/user-manuals/03-goods-receipts.md) · [`docs/user-manuals/04-internal-requests.md`](docs/user-manuals/04-internal-requests.md) · [`docs/user-manuals/05-edge-cases-and-limits.md`](docs/user-manuals/05-edge-cases-and-limits.md) · [`docs/user-manuals/06-admin-reference.md`](docs/user-manuals/06-admin-reference.md) · [`docs/user-manuals/07-manager-catalog.md`](docs/user-manuals/07-manager-catalog.md) · [`docs/user-manuals/08-request-threads.md`](docs/user-manuals/08-request-threads.md)
- [`docs/archive/warehouse-tenancy-setup.md`](docs/archive/warehouse-tenancy-setup.md) — archived Branch/Membership sketch (superseded)
- [`AGENTS.md`](AGENTS.md)
- [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — development pace
- [`products/README.md`](products/README.md) — historical catalogue build log

---

## What is explicitly not built yet

Canonical list of “next / later” is the phase table in [`docs/handoff.md`](docs/handoff.md). In short:

- **Email automation** (Phase 6 — wire notify stubs to real email)
- Shared chrome / branch phone UX / console polish; offline / PWA / OAuth
- Integration tests (unit suites are green, **489 tests**)
- Login rate limiting (pre-production blocker; documented in `config/settings/base.py`)
