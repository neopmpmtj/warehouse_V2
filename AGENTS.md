# CentCompras — Agent instructions

Django 6.1 + PostgreSQL MVP for a **central warehouse** with **satellite branches**. Catalogue + pricing + purchase orders + goods receipt & stock + manager catalog (Phases 0–4) are done, plus **branches tenancy + catalog + requisição + goods issue + branch receipt (Phase 5, complete)**. Email and offline are deferred.

**▶ Read [`docs/handoff.md`](docs/handoff.md) first** — condensed state, locked decisions, and the exact next task. Then [`README.md`](README.md) for setup and [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) for sequencing. Reviews are concluded and archived: [`docs/archive/code-review-full-2026-08-21-1303.md`](docs/archive/code-review-full-2026-08-21-1303.md) (N1–N12) and [`docs/archive/code-review-full-2026-08-20-2208.md`](docs/archive/code-review-full-2026-08-20-2208.md) (P0–P4). The 24 Aug threads review **M1–M5 and L1–L6 are applied** ([`docs/reviews/threads-review-2026-08-24.md`](docs/reviews/threads-review-2026-08-24.md); leftover N1–N6 nits optional). Company Voice review **H1, M1–M9, L1–L8 are applied** ([`docs/reviews/company-voice-review-2026-08-24-1010.md`](docs/reviews/company-voice-review-2026-08-24-1010.md); leftover N1–N3 nits optional).

## Session handoff (August 2026)

**Done:** Auth (email + warehouse groups + per-user timezone), catalog management + audit, item console, **pricing** (selling prices + `SupplierItemPrice`), **purchase orders** (`procurement` app: lines, discounts, approval workflow, approved-totals snapshot, email stub), **goods receipt + stock ledger** (`inventory` app: `GoodsReceipt`/`GoodsReceiptLine`, `StockMovement` signed ledger, cached `Item.quantity`, `receive_goods()` + admin-only `adjust_stock()`), **manager catalog** (read-only `/manage/catalog/`), **branches tenancy + catalog + requisição + goods issue + branch receipt + polish — Slices 1–6 (Phase 5 complete)** (`branches` app: `Branch`/`BranchMembership`, `ActiveBranchMiddleware`, `/branch/select/` picker, `/branch/catalog/` + API with cost hidden + stock hint, admin, seed, role-based post-login redirect; `orders` app: `InternalRequest` + lines, manager caps, branch workflow through `approved`; `inventory` `GoodsIssue` + `issue_goods`, `/manage/internal-requests/`, short-close, `/manage/branch-approval-limits/`, branch receipt + branch stock ledger: `BranchReceipt`/`BranchStockMovement`/`BranchItemStock`, `receive_at_branch`, `/branch/receipts/`, `adjust_branch_stock`; seed sample requisições + `04-internal-requests.md`), **item `internal_code` Phases 1–2** (format charset; immutability after first save; mandatory Genesis with atomic console create; qualification gates; console UI + i18n; user manuals; `add_item` CLI), **requisição/receipt bug fixes** (validation messages, branch receipt UX, warehouse short-close), **`/session-handoff`** skill + slash command, dev seed script, **manage-page Settings gear + popover** (items, catalog, POs, goods receipts), **sub-families catalogue slice** (`SubFamily` + optional `Item.sub_family`; console drawer/filter/form; manager catalog column+filter; branch catalog column; seed + `add_item --sub-family`; migration `0009_subfamily.py`), **warehouse FIFO stock reservation (D32)** (`InternalRequestLine.quantity_reserved` at approve; available = on-hand − reserved; issue only from the line's hold; incoming stock auto-allocates FIFO), **request threads (catalogue-gap requests)** (`threads` app: branch opens a written thread for items **not in the catalogue**; warehouse engages; item created via item console and linked; opener-only close with reason; branch manager/admin + warehouse admin force-close override; `awaiting_warehouse`/`awaiting_branch`/`closed` states; unread via `ThreadReadState`; other-branch 404; capability-based warehouse gate — no `threads.*` perms), **request-threads review (24 Aug 2026)** (read-only review — **5 Medium / 6 Low / 6 Nit, no Critical/High**; report [`docs/reviews/threads-review-2026-08-24.md`](docs/reviews/threads-review-2026-08-24.md)), **request-threads review fixes M1–M5 and L1–L6** (400s for bad JSON/`branch_id`; prefetch; hide stale dialogs; opener-only satisfaction; link unknown-id 400; explicit mark-read POST; empty-state; warehouse search gate; create membership check; int-only satisfaction), **Company Voice** (`company_voice` app: company-wide suggestion box at `/company-voice/`; 15-minute edit window; creator-only soft delete; one sub-thread per post), **Company Voice review (24 Aug 2026)** (two sub-agents + parent; **1 High / 9 Medium / 8 Low / 3 Nit**; report [`docs/reviews/company-voice-review-2026-08-24-1010.md`](docs/reviews/company-voice-review-2026-08-24-1010.md)), **Company Voice review fixes H1, M1–M9, L1–L8** (`edited_at`; JSON 400; post row lock; PATCH 409; live `comment_count`; inspect-only admin; `VoiceChangeLog`; Refresh + draft preserve; boolean anonymous; i18n codes).

**Not done:** leftover Company Voice nits N1–N3 (optional), leftover threads-review nits N1–N6 (optional), offline, shared chrome, branch phone UX, remaining console polish (`/` and `/branch/…` headers), production OAuth/deployment, **Phase 6 email automation**.

**Next:** **Phase 6 — email automation** — wire `notify_supplier_on_approval` (and related stubs) to real email (SMTP/provider); templates EN + pt-PT. See [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) §13. Warehouse FIFO reservation plan is **complete** ([`.cursor/plans/stock_reservation_fifo_c7e19b04.plan.md`](.cursor/plans/stock_reservation_fifo_c7e19b04.plan.md)). Sub-families plan is **complete** ([`.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md`](.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md)). Item `internal_code` plan is **complete** ([`.cursor/plans/internal_code_format_rules_7862515a.plan.md`](.cursor/plans/internal_code_format_rules_7862515a.plan.md)). Do **not** use tenancy-doc §6–7 Order stub.

**Stock today:** `Item.quantity` is a cached **physical** balance written **only** via `StockMovement` (never typed directly); DB `CheckConstraint item_quantity_gte_zero`. **Available** = on-hand − `sum(quantity_reserved)` on `approved`/`fulfilling` lines (D32). Approve holds `min(remaining, unreserved on-hand)` and never fails for lack of stock; issue ships only from that line's reserved qty; incoming stock auto-allocates FIFO; negative `adjust_stock` cannot go below total reserved when reserved > 0. No `StockMovement.Type.RESERVE`. Selling prices are **manual**; cost prices are **dynamic** from `SupplierItemPrice` (one `primary` per item, DB-enforced). PO lines are **rejected** if the supplier has no price for the item, or if the same item is added twice; `approved_net/vat/gross` are frozen at approval. Warehouse group assignment is exclusive and resets grade to 1. Approval uses grades + `ApprovalLimit` (EUR gross); reject/manual close/`adjust_stock` require a reason. Selling prices & `reorder_level` must be finite and ≥ 0 (DB `CheckConstraint`s); PO line quantity capped at 1e9; login rate limiting is a documented pre-production blocker (deferred).

## User roles (do not confuse these)

| Role | Flag / model | Catalog | Orders (future) |
|------|----------------|---------|-----------------|
| Warehouse admin | group `warehouse_admins` | Full catalogue (view/add/change/delete) via the website; approve any PO; edit `/manage/approval-limits/` | N/A (central) |
| Warehouse manager | group `warehouse_managers` | Grade 1: mutate closed circuit, no approve. Grade 2+: approve within `ApprovalLimit` caps (no delete) | N/A (central) |
| Warehouse operator | group `warehouse_data_operators` | Grade 1 view-only; grade 2 mutate closed circuit. Never approve | N/A (central) |
| Branch admin / manager / operator | `BranchMembership.role` (Phase 5 done) | Read-only catalog + requisição interna + branch receipt (all done) |
| Django superuser | `is_superuser` | May use the website console; **only** role that can log into `/admin/` | Site config in `/admin/` |

Dev seed: `./scripts/seed_dev_data.sh` → warehouse users `warehouse.admin@centcompras.dev`, `warehouse.manager@…` / `manager2` / `manager3`, `warehouse.operator@…` / `operator2`; branch users `branch.operator|manager|admin.north@…`, `branch.operator|manager.south@…`, `branch.dual@…` (both branches). Password `devpass123`.

## Current state (what exists)

### Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom `User` (email login, timezone, `warehouse_grade`), login/logout, warehouse groups, timezone middleware, `authz.py`, `capabilities.py` |
| `products` | Catalogue + pricing: model, service layer, API, staff admin, staff console, tests |
| `procurement` | Purchase orders: models, service layer, console API, admin, tests |
| `inventory` | Goods receipt + stock ledger + goods issue + FIFO reservation helpers + branch stock: `GoodsReceipt`/`GoodsIssue`/`BranchReceipt`/`StockMovement`/`BranchStockMovement`/`BranchItemStock`, services, console API, admin, tests |
| `branches` | Tenancy + catalog (Slices 1–2): `Branch`/`BranchMembership`, `ActiveBranchMiddleware`, `/branch/select/` picker, `/branch/catalog/` + API, admin, services, tests |
| `orders` | Internal request (requisição interna): models (incl. `quantity_reserved`), services, console API, web UI, admin, tests |
| `threads` | Request threads (catalogue-gap requests): `ItemRequestThread`/`ThreadMessage`/`ThreadReadState`/changelog, services, console API, web UI, admin, tests |
| `company_voice` | Company-wide suggestion box: `VoicePost`/`VoiceSubThread`/`VoiceComment`, services, console API, feed UI, admin, tests |
| `logging_utils` | `get_logger("centcompras.<app>")`, rotating logs in `logs/` |

### Auth

- `AUTH_USER_MODEL = "accounts.User"`
- Warehouse roles via Django groups: `warehouse_admins` / `warehouse_managers` / `warehouse_data_operators`
- Catalogue and API require login; API returns 401 when unauthenticated
- Google OAuth planned for production — not implemented in dev
- **Branches + requisição + goods issue + branch receipt built (Phase 5 complete)** — `Branch`/`BranchMembership` (`operator`/`manager`/`admin`), `ActiveBranchMiddleware`, `/branch/select/` picker, `/branch/catalog/` (cost hidden, stock hint), `/branch/requests/` (requisição through `approved`, manager caps), `/manage/internal-requests/` (goods issue, short-close), `/branch/receipts/` (branch receipt + branch stock); warehouse groups never imply branch access and vice versa

### Catalogue

- **Item fields:** family, optional `sub_family`, `internal_code` (required on console create; immutable after first save), `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active`, timestamps, plus **3 manual selling prices** (`retail_price`, `wholesale_price`, `special_price`) and a cached `quantity` balance (updated via `StockMovement`). Suppliers are independent master data.
- **Sub-families:** two-level taxonomy `FamilyProduct` → `SubFamily`; optional on items; CI-unique name per family; immutable name/parent after create; D16 activity (no cascade).
- **Audit:** `ItemChangeLog`, `FamilyChangeLog`, `SubFamilyChangeLog`, `SupplierChangeLog`, `SupplierItemPriceChangeLog` — who changed what (create / update / deactivate / reactivate). Item lifecycle reasons required; family/supplier/sub-family deactivate is confirm-only
- **Names:** family, sub-family (per parent), and supplier names are case-insensitive unique; family and sub-family names are **immutable** (create-only) and the console UI does not rename them
- **Global catalogue** — no `branch_id` on `Item`
- **Management:** warehouse users via `/manage/items/` (groups `warehouse_admins` / `warehouse_managers` / `warehouse_data_operators` and Django model permissions). Django admin (`/admin/`) is **superuser only**. All mutations through `products/services.py`
- **Validation:** `internal_code` charset + uniqueness; immutability after save; Genesis qualification on first activation; duplicate non-empty `internal_code` rejected in services/admin
- **CLI:** `add_item` for dev/bootstrap (audit user is null); `--internal-code` required; use `--retail-price` and `--activate` for Genesis (retail must be > 0)
- **Tests:** `.venv/bin/python manage.py test products`

### Logging

- `logging_utils` — console + `logs/*.log` (gitignored)
- Loggers: `centcompras.products`, `centcompras.procurement`, `centcompras.inventory`, `centcompras.branches`, `centcompras.accounts`, `centcompras.django`, etc.
- Config: `logging_utils/logging_config.py`

PostgreSQL is the source of truth.

## Not implemented yet

- **Email automation** (Phase 6 — wire notify stubs to real email; Phase 5 is complete)
- Order business rules not locked (stock timing, cart shape, cancel policy)
- Shared page chrome; branch phone-catalogue UX; staff console polish (dedicated sessions)
- Integration tests
- Google OAuth, public signup, password reset
- Email automation (supplier notification — stub exists)
- Offline order queue and sync; in-app branch switcher
- Catalog extras: categories, vector/LLM search, bulk import

Full list: [`README.md` → What is explicitly not built yet](README.md#what-is-explicitly-not-built-yet)

## Architecture conventions

```text
CLI / API / views  →  services.py  →  models.py  →  PostgreSQL
```

- Business logic in `services.py`, not views or management commands
- Catalog/PO/inventory management via Django groups + model permissions (`products`, `procurement`, `inventory` apps)
- Branch tenancy (`branches`, `request.active_branch`) is built; Phase 5 complete
- Plain Django + plain JavaScript — no React, Vue
- One concept per phase; no large application dumps

## Documentation conventions

- **Always put a full timestamp (date + time) in document filenames** — e.g. `code-review-full-2026-08-20-1928.md` (format `YYYY-MM-DD-HHMM`). The timestamp makes the chronological order self-evident when many similarly-named docs accumulate.
- Reviews/audits are worked to completion, marked done, then archived under `docs/archive/` — never left as a live backlog. Both the 2208 and 1303 reviews are concluded and archived.
- [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) is the **living plan** (sequencing + status tracker + locked decisions) — tick its status tracker every session.
- **End of session:** run slash command `/session-handoff` or skill `session-handoff` (`.cursor/skills/session-handoff/SKILL.md`) to sync handoff, PROJECT-PLAN, README, plans, and manuals.

## Commands

```bash
source .venv/bin/activate
cp config/settings.example.py config/settings.py   # first time only
python manage.py migrate
python manage.py createsuperuser                 # optional site admin
./scripts/seed_dev_data.sh                         # warehouse + branch users, families, suppliers, items, prices
python manage.py runserver
python manage.py test products accounts procurement inventory branches orders --noinput
```

**Tests:** always use the project virtualenv — do not use system `python`/`python3`. Either activate first (`source .venv/bin/activate`) or invoke the venv interpreter directly. Recreate without `--keepdb` if the test DB is stale after `TransactionTestCase`.

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders threads company_voice --noinput
```

Use one hostname consistently for offline testing (`localhost` or `127.0.0.1`, not both).

## Security

- Do not commit `config/settings.py`, `.env`, or credentials
- Do not add product creation or editing from the branch phone UI or public web unless explicitly requested

## Before large changes

1. [`docs/handoff.md`](docs/handoff.md) — state + decisions + next task
2. [`README.md`](README.md) — setup, URLs, seed
3. [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) — phased plan
4. [`docs/archive/phase5-roadmap-260821-1618.md`](docs/archive/phase5-roadmap-260821-1618.md) — Phase 5 roadmap (archived); [`docs/archive/warehouse-tenancy-setup.md`](docs/archive/warehouse-tenancy-setup.md) is archived sketch only
