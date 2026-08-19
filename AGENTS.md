# CentCompras — Agent instructions

Django 6.1 + PostgreSQL MVP for a **central warehouse** with **satellite branches**. Branch staff browse a product catalogue from a phone browser. **Inbound stock** (supplier purchases → product quantity) is the next product-side design; **branch orders** wait until stock can be received.

**Read [`README.md` → Project status (handoff)](README.md#project-status-handoff) first** for what is done vs pending.

Staff product console (this phase): [`docs/product-console-session-2026-08-18.md`](docs/product-console-session-2026-08-18.md) — request, stack, decisions, bugs. Follow-ons: [sort + lifecycle](docs/product-console-session-2026-08-18-sort-lifecycle.md), [family + supplier](docs/product-console-session-2026-08-18-family-supplier.md), [family + supplier audit](docs/product-console-session-2026-08-18-family-supplier-audit.md).

## Session handoff (August 2026)

**Done:** Auth/tenancy, offline catalogue, catalog management (admin + audit + soft delete), staff product console (`/manage/products/` — sort, inactive-by-default create, family/supplier drawers), family and supplier PostgreSQL audit logs, catalog polish, dev seed script with **warehouse user**. Handoff docs synced 18 August 2026 (`aux_instructions.md`, tenancy preamble, this file, root README).

**Not done:** inbound stock / procurement app, `orders` app, offline order queue, shared page chrome, branch phone UX, console polish, integration tests for auth/branches, production OAuth/deployment.

**Next:** Design how a supplier purchase becomes `Product.stock`. Do **not** implement `orders/` or the tenancy-doc Order stub. Hold shared chrome, `/` restyle, and console polish for dedicated sessions.

**Stock today:** `Product.stock` is still typed in the staff console. That is not a locked design.

## User roles (do not confuse these)

| Role | Flag / model | Catalog | Orders (future) |
|------|----------------|---------|-----------------|
| Warehouse staff | `User.is_staff` | Manage via `/manage/products/` (and `/admin/products/`); stock is still typed on the product | N/A (central) |
| Branch admin/manager/user | `BranchMembership.role` | Read-only at `/` | Per-branch permissions in `branches/permissions.py` (after inbound stock) |
| Django superuser | `is_superuser` | Only if also `is_staff` | Site config in `/admin/` |

Dev seed: `./scripts/seed_dev_data.sh` → `warehouse@centcompras.dev` + 3 branch admins, password `devpass123`.

## Current state (what exists)

### Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom `User` (email login), login/logout |
| `branches` | `Branch`, `BranchMembership`, `permissions.py`, `ActiveBranchMiddleware`, branch picker, `seed_dev_data` command |
| `products` | Catalogue model, service layer, API, CLI, offline web UI, staff admin, staff console, tests |
| `logging_utils` | `get_logger("centcompras.<app>")`, rotating logs in `logs/` |

### Auth and tenancy

- `AUTH_USER_MODEL = "accounts.User"`
- Roles per branch via `BranchMembership`: admin, manager, user
- Active branch in session (`active_branch_id`); auto-set for single-branch users
- Catalogue and API require login; API returns 401 when unauthenticated
- Google OAuth planned for production — not implemented in dev
- Logout on no-branch page uses POST form (Django 6.1 `LogoutView`)

### Catalogue

- **Product fields:** family, optional `internal_code`, `description`, `stock` (still console-editable), `price`, `unit_of_measure`, `reorder_level`, `is_active` (new products start inactive), timestamps; suppliers via `ProductSupplier`
- **Audit:** `ProductChangeLog`, `FamilyChangeLog`, `SupplierChangeLog` — who changed what (create / update / deactivate / reactivate). Product lifecycle reasons required; family/supplier deactivate is confirm-only
- **Names:** family and supplier names are case-insensitive unique; the console does not rename them
- **Global catalogue** — no `branch_id` on `Product` (warehouse stock for all branches)
- **Management:** warehouse staff via `/manage/products/` (products, families, suppliers) and Django admin (`is_staff`); all mutations through `products/services.py`
- **Branch access:** read-only — `GET /api/products/` returns active products only plus `catalog_updated_at`
- **Validation:** duplicate non-empty `internal_code` rejected in services/admin
- **CLI:** `add_product` for dev/bootstrap (audit user is null); optional `--internal-code`
- **Offline:** Service Worker (`centcompras-shell-v5`) + IndexedDB (read-only catalogue cache)
- **Tests:** `.venv/bin/python manage.py test products`

### Logging

- `logging_utils` — console + `logs/*.log` (gitignored)
- Loggers: `centcompras.products`, `centcompras.branches`, `centcompras.django`, etc.
- Config: `logging_utils/logging_config.py`

PostgreSQL is the source of truth. IndexedDB is a read-only local cache.

## Not implemented yet

- Inbound stock / procurement (supplier receipt → `Product.stock`) — **next design**
- `orders` app and order workflow (**after** inbound stock)
- Order business rules not locked (stock timing, cart shape, cancel policy)
- Shared page chrome; branch phone-catalogue UX; staff console polish (dedicated sessions)
- Integration tests for auth, branch middleware, offline catalogue
- Tests for `accounts` and `branches` (stubs only)
- Google OAuth, public signup, password reset
- Offline order queue and sync
- In-app branch switcher
- Catalog extras: categories, vector/LLM search, bulk import

Full list: [`README.md` → What is explicitly not built yet](README.md#what-is-explicitly-not-built-yet)

## Architecture conventions

```text
CLI / API / views  →  services.py  →  models.py  →  PostgreSQL
```

- Business logic in `services.py`, not views or management commands
- Tenant permission checks via `branches/permissions.py`; catalog management via `products/permissions.py` (`is_staff`)
- Use `request.active_branch` (set by middleware) for branch-scoped features
- Pass pre-fetched `memberships` to `get_active_branch(request, memberships)` to avoid duplicate queries
- Plain Django + plain JavaScript — no React, Vue
- One concept per phase; no large application dumps

## Commands

```bash
source .venv/bin/activate
cp config/settings.example.py config/settings.py   # first time only
python manage.py migrate
python manage.py createsuperuser                 # optional site admin
./scripts/seed_dev_data.sh                         # branches, users, warehouse, products
python manage.py runserver
python manage.py test products accounts branches
```

**Tests:** always use the project virtualenv — do not use system `python`/`python3`. Either activate first (`source .venv/bin/activate`) or invoke the venv interpreter directly:

```bash
.venv/bin/python manage.py test products accounts branches
```

Use one hostname consistently for offline testing (`localhost` or `127.0.0.1`, not both).

## Security

- Do not commit `config/settings.py`, `.env`, or credentials
- Do not add product creation or editing from the branch phone UI or public web unless explicitly requested

## Before large changes

1. [`README.md`](README.md) — project status and scope
2. [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — tenancy (done); Order sketch §6–7 is **not** the next build
3. [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — development pace
