# CentCompras — Central Warehouse

A Django web application for a company with a **central warehouse** and **satellite branches**. Branch staff browse the product catalogue from a phone browser and will eventually place orders against central stock — including in areas with poor mobile coverage.

This repository is an early-stage MVP built incrementally: one concept per phase, with clear separation of responsibilities and no unnecessary frameworks.

---

## Project status (handoff)

*Last updated: 19 August 2026 — read this section first when resuming work.*

### Where we stand

The **item catalogue + pricing** is the current module: warehouse staff create and manage **items**, **families**, and **suppliers** at `/manage/items/`. Items start inactive until Genesis and carry **three manual selling prices** (retail / wholesale / special). **Cost prices are dynamic**, held per supplier in a `SupplierItemPrice` table (the source for later purchase orders). There is **no stock** — quantity waits for the inbound-receipt design. Branch orders wait until then.

Held for later dedicated sessions (do not start in passing): shared page chrome, branch phone-catalogue UX, staff-console polish.

### Completed

| Phase | Status | Notes |
|-------|--------|-------|
| **Product catalogue MVP** | Done | Model, API, offline HTML/JS, Service Worker, IndexedDB — see [`products/README.md`](products/README.md) |
| **Auth foundation** | Done | `accounts` (email login), warehouse groups |
| **Login-protected catalogue** | Done | `/` and `/api/products/` require session; API returns 401 when logged out |
| **Centralized logging** | Done | `logging_utils` → rotating files in `logs/` |
| **Catalog management & audit** | Done | Item / family / supplier lifecycle, `ItemChangeLog` + `FamilyChangeLog` + `SupplierChangeLog`, soft delete, staff admin via `products/services.py` |
| **Catalog polish** | Done | Duplicate `internal_code` validation; optional item audit `reason` |
| **Staff item console** | Done | `/manage/items/` — table, filters, column sort, inactive-by-default create + Genesis, family/supplier drawers, EN/pt-PT, light/dark |
| **Family & supplier priors** | Done | Console create/deactivate; case-insensitive unique names (no rename in the console UI); PostgreSQL audit logs |
| **Pricing (selling + supplier cost)** | Done | 3 manual selling prices on `Item`; `SupplierItemPrice` (supplier × item cost, one primary) + audit; console, admin, API, seed |
| **Dev seed script** | Done | [`scripts/seed_dev_data.sh`](scripts/seed_dev_data.sh) — branches, branch users, **warehouse user**, sample products |
| **Project setup docs** | Done | Root README, `requirements.txt`, `config/settings.example.py`, `AGENTS.md`, `.cursor/` rules |

**Design choices locked in for later phases:**

- `Item` catalogue is **global** (central warehouse) — no `branch_id` on items.
- **Catalog mutations** = warehouse groups on the website (`warehouse_admins` full, `warehouse_managers` add/change, `warehouse_data_operators` view). **`/admin/` is superuser only.**
- Dev login: email + password. Production: **Google OAuth** (not implemented yet).
- Users are provisioned in admin or seed script — no public signup.
- Orders (future, after inbound stock) will be **branch-scoped** with `branch` + `created_by` FKs. The sketch in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6 is **not** an implementation spec (`item_name` is leftover).
- **Items have no stock field** (inbound receipts will become the source of quantity later). Selling prices are **manual**; **cost prices are dynamic** from `SupplierItemPrice`.

### User roles (important — practice with these)

| User type | Example (after seed) | Can do today |
|-----------|----------------------|--------------|
| **Warehouse admin** | `warehouse.admin@centcompras.dev` | Full catalogue on `/manage/items/` (`warehouse_admins`). Cannot log into `/admin/`. |
| **Warehouse manager** | `warehouse.manager@centcompras.dev` | Add/edit catalogue (`warehouse_managers`). No delete permission. |
| **Warehouse operator** | `warehouse.operator@centcompras.dev` | Read-only catalogue (`warehouse_data_operators`). |
| **Branch admin** | `admin.lisbon@centcompras.dev` | Log in, browse catalogue at `/` (read-only); future: orders in their branch (after inbound stock exists) |
| **Branch manager / user** | (create in admin) | Same browse access; different order permissions later |
| **Django superuser** | from `createsuperuser` | Site admin at `/admin/`: users, groups, memberships. The only users who may use the Django admin. |

After `./scripts/seed_dev_data.sh`, all seeded users share password **`devpass123`**.

### Not started / pending

| Area | Priority | Notes |
|------|----------|-------|
| **Inbound stock / procurement** | **Next (design)** | Warehouse buys from suppliers; a receipt should **write product stock**, not a person typing it on the product row. No app yet — agree the smallest first slice before coding. |
| **Orders workflow** | After inbound stock | Branch requests against central stock. Sketch only: [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6–7. Do not implement the stub `item_name` model. |
| **Order business rules** | Before coding orders | Multi-line cart vs single line; stock decrement timing; cancel/edit policy |
| **Shared page chrome** | Later session | Same header/CSS on login, branch picker, `/`, so new pages do not look like a different app |
| **Branch phone catalogue UX** | Later session | Search, family, unit, human stock/price — hold; `/` stays a scaffold until that session |
| **Staff console polish** | Later session | History diffs, default Active filter, Genesis copy — hold |
| **Tests (accounts/branches)** | Later | `accounts/tests.py`, `branches/tests.py` still stubs; `products/tests.py` covers catalogue + console (~86 tests) |
| **Integration tests** | Later | Full auth → branch middleware → catalogue API → offline flow |
| **Google OAuth** | Production | `django-allauth` or similar |
| **Public signup / password reset** | Later | |
| **Branch switcher in catalogue** | Later | Multi-branch users pick at login only; no in-app switch |
| **Production deployment** | Later | HTTPS, env secrets, PWA manifest |
| **Catalog extras (deferred)** | Later | Categories extras, LLM/vector search on `description`, bulk import |

### Recommended next session

1. Read this section, [User roles](#user-roles-important--practice-with-these), and the staff console session reports: [`docs/product-console-session-2026-08-18.md`](docs/product-console-session-2026-08-18.md), [sort + lifecycle](docs/product-console-session-2026-08-18-sort-lifecycle.md), [family + supplier](docs/product-console-session-2026-08-18-family-supplier.md), [family + supplier audit](docs/product-console-session-2026-08-18-family-supplier-audit.md).
2. Fresh environment: `python manage.py migrate` then `./scripts/seed_dev_data.sh`.
3. Practice: warehouse user → `/manage/items/`; create a family if needed; new item starts inactive until Genesis; Families / Suppliers drawers show History.
4. **Design inbound stock** (procurement / goods receipt) only after items exist: how a supplier purchase will later write quantity. Do not start `orders/` until stock can be received.
5. Do **not** in passing: restyle `/`, polish the staff console, or implement the tenancy-doc `Order` stub.

### Key files (catalog — current module)

```text
products/models.py           Item, FamilyProduct, Supplier, VatRate, change-log models
products/services.py         create/update/deactivate/reactivate items, families, suppliers
products/permissions.py      view/add/change checks on /api/manage/
accounts/groups.py           warehouse_admins / managers / data_operators + superuser-only /admin/
products/admin.py            superuser-only admin + audit inlines
products/views.py            staff dashboard at `/`
products/console_views.py    Staff console page + /api/manage/ items, families, suppliers
products/tests.py            Catalog + console tests — run: python manage.py test products
products/management/commands/seed_dev_data.py
scripts/seed_dev_data.sh     wrapper: migrate + seed
```

Migrations: `products/0001_initial.py` through `0005` (inactive-by-default, CI unique names, family/supplier audit). Run `migrate` after pull if schema changed.

### Development philosophy

One concept per phase. Reusable `services.py` layer. Plain Django + plain JavaScript. Do not dump a finished application in one step. See [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md).

---

## Business scenario

- A central warehouse holds the master product catalogue and stock levels. **Today, stock is typed on the product.** The next product-side work is recording supplier receipts so that quantity is filled from purchases, not from the product form.
- Branch users access a lightweight web app (plain HTML + JavaScript) from their phones. **Branch orders wait** until inbound stock exists.
- Users may travel through areas with little or no mobile data, so the client must work **offline** for catalogue browsing (and, in a future phase, for queuing orders).
- PostgreSQL on the server is the **source of truth**. The browser's IndexedDB is a **read-only local cache** of the last successfully downloaded catalogue.

Warehouse staff manage the catalogue at `/manage/items/` via three Django groups (`warehouse_admins`, `warehouse_managers`, `warehouse_data_operators`). Django admin is reserved for superusers.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django 6.1 |
| Database | PostgreSQL (`centcompras_db`) |
| Frontend | Plain HTML, plain JavaScript |
| Offline | Service Worker (app shell), IndexedDB (catalogue data) |
| Logging | `logging_utils` — console + rotating files in `logs/` |

No React, Vue, or similar frontend framework.

---

## What works today

### Authentication

- Custom `User` model (`accounts`) — email login, no username field
- Session login/logout at `/accounts/login/` and `/accounts/logout/`
- Warehouse roles via Django groups (`warehouse_admins` / `warehouse_managers` / `warehouse_data_operators`)
- Django admin (superuser only) for users and groups
- Catalogue requires login; API returns 401 when unauthenticated

> **Branches (tenancy) are NOT built yet.** The `branches` app (`Branch`, `BranchMembership`, active-branch middleware, picker) is documented in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) but **deferred** until after inbound stock. There is no `branches/` directory in the code today.

Production will use Google OAuth (not implemented in dev — email/password login only).

### Item catalogue (server)

- `Item` model: required `family`, optional `internal_code`, `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active` (soft delete; **new items start inactive**), timestamps, plus three **manual selling prices** — `retail_price`, `wholesale_price`, `special_price`. No stock.
- `SupplierItemPrice` model: `supplier` × `item` → `cost_price` + `primary` (one primary per item). This is the **dynamic cost source** for later purchase orders. Audit via `SupplierItemPriceChangeLog`.
- `FamilyProduct` / `Supplier` — family is required on item create; suppliers are independent master data (not linked to items yet). Names are case-insensitive unique. The console UI does not rename them.
- Audit: `ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog` — who changed what (create / update / deactivate / reactivate). Item deactivate/reactivate require a reason; family/supplier lifecycle does not.
- Service layer in [`products/services.py`](products/services.py): item, family, and supplier mutations.
- Warehouse staff manage the catalogue in `/manage/items/` using Django model permissions on three groups. Django admin is superuser only.
- Dev/bootstrap CLI:

  ```bash
  python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16
  python manage.py add_item "Steel Pipe" --family Pipes --vat-rate VAT16 --internal-code PIPE-20
  ```

- Staff JSON APIs (authenticated warehouse groups):

  ```text
  GET /api/manage/items/
  GET /api/manage/families/
  GET /api/manage/suppliers/
  ```

- `ItemChangeLog.reason` — required for item deactivate/reactivate; optional on field edits. Family/supplier logs store an empty reason today.
- Duplicate non-empty `internal_code` values are rejected with a clear validation error in admin and services.
- Tests in [`products/tests.py`](products/tests.py) cover service diffs, active filtering, uniqueness, console APIs, and audit logs.

### Item console (browser)

- Staff dashboard at `/` (catalogue view permission required).
- Item console at `/manage/items/` — table, filters, family and supplier drawers.
- The console is online-only (not part of a catalogue app-shell cache).

### URL layout

| Path | Purpose |
|------|---------|
| `/` | Staff dashboard (catalogue view permission) |
| `/manage/items/` | Warehouse item console (view permission) |
| `/api/manage/items/` | Warehouse item JSON API (view; writes need add/change) |
| `/api/manage/families/` | Warehouse family JSON API (view; writes need add/change) |
| `/api/manage/suppliers/` | Warehouse supplier JSON API (view; writes need add/change) |
| `/accounts/login/` | Email + password login |
| `/accounts/logout/` | Log out |
| `/service-worker.js` | Parked uninstall stub |
| `/admin/` | Django admin (**superuser only**) |

---

## Project structure

```text
warehouse/
├── manage.py
├── requirements.txt
├── config/
│   ├── settings.example.py   # copy to settings.py locally
│   ├── urls.py
│   └── ...
├── accounts/                 # custom User, login/logout
├── branches/                 # Branch, BranchMembership, active branch middleware
├── logging_utils/            # centralized logging (console + logs/)
├── AGENTS.md                 # Cursor agent instructions
├── .cursor/                  # Cursor rules and commands
├── docs/
│   └── warehouse-tenancy-setup.md
└── products/                 # catalogue app
    ├── models.py
    ├── services.py
    ├── views.py
    └── ...
```

The `products/README.md` file is a step-by-step record of how the catalogue and offline layer were built.

---

## Setup

First-time setup from a fresh clone. Run all commands from the project root (`warehouse/`).

### 1. Virtual environment and dependencies

```bash
cd warehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL

The app expects database `centcompras_db` and user `postgres` (local dev). Adjust in `config/settings.py` if your setup differs.

Enter PostgreSQL as the `postgres` system user:

```bash
sudo -u postgres psql
```

Create the database:

```sql
CREATE DATABASE centcompras_db;
```

If you need to set or reset the `postgres` user password (must match `config/settings.py`):

```sql
ALTER USER postgres WITH PASSWORD 'your_password_here';
\q
```

### 3. Django settings

`config/settings.py` is gitignored (may contain credentials). Copy the example and edit it:

```bash
cp config/settings.example.py config/settings.py
```

Edit `config/settings.py` — set your real database password:

```python
DATABASES = {
    "default": {
        ...
        "PASSWORD": "your_actual_password",  # same as postgres user above
        ...
    }
}
```

### 4. Migrate and create site admin

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # prompts for email + password (not username)
```

`createsuperuser` creates a **site admin** for `/admin/`. That user can manage branches and users but **cannot browse the catalogue** until you also add a `BranchMembership` (step 5).

### 5. Seed test data

**Quick seed (recommended for local learning):**

```bash
chmod +x scripts/seed_dev_data.sh   # first time only
./scripts/seed_dev_data.sh
```

This creates:

| Item | Details |
|------|---------|
| **Branches** | Lisbonbranch, portobranch, vilarealbranch |
| **Branch users** | `admin.lisbon@…`, `admin.porto@…`, `admin.vilareal@…` — **branch admin** role in their branch |
| **Warehouse users** | `warehouse.admin@…` / `warehouse.manager@…` / `warehouse.operator@…` — groups `warehouse_admins`, `warehouse_managers`, `warehouse_data_operators` |
| **Items** | ~50 sample items via `products/services.py` |
| **Password** | `devpass123` for all seeded users (override with `--password`) |

Re-running the script is safe (idempotent). Options: `--skip-items`, `--skip-warehouse`.

**Important:** branch **admin** role is for future **order** permissions per branch. **Catalogue** access is the warehouse groups above, not Django admin.

**Manual seed (via `/admin/`)** — if you prefer to practice admin UI:

Start the dev server:

```bash
python manage.py runserver
```

Open `http://localhost:8000/admin/` and log in with the superuser.

Create records in this order:

| Step | Admin model | What to do |
|------|-------------|------------|
| 1 | **Branches** | Add 2–3 branches (e.g. Lisbon, Porto) |
| 2 | **Users** | Add branch users (email + password) — separate from superuser for realistic testing |
| 3 | **Branch memberships** | Link each user to a branch with a role (admin, manager, or user) |

**Notes:**

- A user with **no** branch membership can log in but sees the “no branch access” page.
- To test the branch picker, give **one user** memberships in **two** branches.

### 6. Add sample products

Items are managed in **`/manage/items/`** by warehouse users (Django groups), or created by the seed script / CLI:

```bash
./scripts/seed_dev_data.sh          # recommended — includes 3 products
python manage.py add_product "Cement 50kg" 100 12.95
```

### 7. Test the application

1. Open `http://localhost:8000/` — you should be redirected to login.
2. Log in as a **branch user** (with at least one membership).
3. One branch → catalogue loads. Multiple branches → branch picker, then catalogue.
4. API (same browser session): `http://localhost:8000/api/products/`

Use **one hostname** consistently (`localhost` **or** `127.0.0.1`, not both) — Service Workers are origin-specific.

### 8. Logging

Application logs are written automatically to `logs/` (gitignored) when the server runs:

| File | Logger name |
|------|-------------|
| `logs/centcompras.log` | General |
| `logs/accounts.log` | `centcompras.accounts` |
| `logs/branches.log` | `centcompras.branches` |
| `logs/products.log` | `centcompras.products` |
| `logs/django.log` | `centcompras.django` (HTTP requests) |

In Python code:

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

First-time or reset DB: steps 1–4 above, then `./scripts/seed_dev_data.sh`.

Practice logins (after seed): `warehouse@centcompras.dev` (catalog admin), `admin.lisbon@centcompras.dev` (branch catalogue), password `devpass123`.

---

## Architecture (current)

```text
PostgreSQL
    ↑
User, Branch, BranchMembership, Product
    ↑
services.py / permissions.py
    ↑
views (login required) → API + HTML
    ↑
product_list.js → IndexedDB

Service Worker → caches HTML + JS (app shell, offline page load)
```

---

## Further reading

- **Start here:** [Project status (handoff)](#project-status-handoff) in this file
- [`docs/product-console-session-2026-08-18.md`](docs/product-console-session-2026-08-18.md) — staff product console: request, stack, decisions, bugs fixed
- [`docs/product-console-session-2026-08-18-sort-lifecycle.md`](docs/product-console-session-2026-08-18-sort-lifecycle.md) — column sort, inactive create, Genesis / activate / deactivate presets
- [`docs/product-console-session-2026-08-18-family-supplier.md`](docs/product-console-session-2026-08-18-family-supplier.md) — family and supplier console priors
- [`docs/product-console-session-2026-08-18-family-supplier-audit.md`](docs/product-console-session-2026-08-18-family-supplier-audit.md) — family/supplier PostgreSQL audit, History in drawers, leftover 1–3
- [`products/README.md`](products/README.md) — **historical** catalogue build log and offline checklist; current facts are in this README’s Project status
- [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — tenancy design (accounts/branches done); **§6–7** is an Order *sketch*, not the next build; see preamble for inbound stock
- [`AGENTS.md`](AGENTS.md) — concise instructions for AI agents in Cursor
- [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — incremental development pace (status synced August 2026)

---

## What is explicitly not built yet

The following do **not** exist today. The [Project status](#project-status-handoff) table above is the canonical handoff reference.

### Business features

- Inbound stock / procurement app — recording supplier purchases so `Product.stock` is filled from receipts
- Stock as a movement ledger (today stock is still typed on the product)
- `orders` app — create, list, edit, delete orders (after inbound stock)
- Shopping cart
- Customers
- Offline order queue in IndexedDB
- Order synchronization when connectivity returns
- Idempotent order submission (client-side order IDs on retry)
- Stock reservation or conflict handling
- Product creation or editing from branch phone UI or public web forms
- In-app branch switcher (only login-time picker for multi-branch users)
- Shared visual chrome on login / branch picker / branch catalogue
- Branch phone-catalogue UX beyond the current scaffold table

### Auth & production

- Google OAuth (production login — dev uses email + password)
- Public signup
- Password reset flow

### Quality & operations

- **Unit tests** — `products/tests.py` covers catalogue and console; `accounts/tests.py` and `branches/tests.py` still stubs
- **Integration tests** — not started
- Production deployment and HTTPS
- PWA manifest / install prompt

### Planned next major phase

**Inbound stock (procurement / goods receipt):** warehouse purchases from suppliers; a data person records the receipt; product stock is updated from that receipt. Branch **ordering** comes after that, so orders are not placed against zero stock.

Ordering (later): branch users create orders online or queue them offline, then sync to the central warehouse with duplicate-safe retries. Builds on existing `Branch`, `BranchMembership`, `permissions.py`, and `request.active_branch`. Do not implement the `item_name` Order stub in the tenancy doc.
