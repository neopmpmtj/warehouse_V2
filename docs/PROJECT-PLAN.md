# CentCompras — Master Project Plan

> **Living document.** Update the [Status tracker](#status-tracker) after every working session: tick `[x]` what is done, add notes, move the "current phase" marker. Keep "Done" sections as a record of decisions, not as a changelog.

- **Last updated:** 21 August 2026, 21:48 WEST
- **Current phase:** Phase 5 **in progress** — phases 0–4 done, **Slices 1–4 (tenancy + catalog + requisição + goods issue) done**, full suite **368 tests green**. Plan authored: [`docs/phase5-plan-260821-1756.md`](phase5-plan-260821-1756.md). Decisions locked in [`docs/phase5-brainstorm-260821-1530.md`](phase5-brainstorm-260821-1530.md); roadmap [`docs/phase5-roadmap-260821-1618.md`](phase5-roadmap-260821-1618.md). **Next:** Slice 5 — branch receipt + branch stock. See [`docs/handoff.md`](handoff.md).
- **Scope of this plan:** the **warehouse products + procurement loop** (central warehouse only). Branch ordering is **next** — see Phase 5 below.

## Status vocabulary

| Marker | Meaning |
|--------|---------|
| ✅ **Done** | Built, tested, shipped |
| 🔜 **Next** | The current work item — actionable now |
| ⏸ **Deferred** | Deliberately postponed (dependency, or a "not now" decision); returns to Next once the reason clears |
| ⏸ **Pending** | Waiting on a trigger/decision; often a stub/seam already exists |
| ⏸ **Future** | Long-term "someday"; no near-term commitment |
| `[x]` / `[ ]` | §15 status-tracker checklist *within* a phase (done / to-do) |

> **"Deferred" is a *decision*, not "not done yet".** It graduates to **Next** when its dependency clears — e.g. Phase 5 was deferred until Phases 0–4 completed.

---

## 1. Purpose

This plan turns the agreed vision into an executable, step-by-step roadmap with status tracking. It is the single source of truth for **sequencing, the status tracker, and locked decisions**. The live session handoff is [`docs/handoff.md`](handoff.md); setup lives in [`README.md`](../README.md).

---

## 2. Vision & corrected business flow

A **central warehouse** buys from suppliers and ships to **satellite branches**. The loop closes only when the warehouse has **stock in house** — that is why we build products/procurement first and branches last.

```
Branch (satellite)                            Central warehouse
    │                                              │
    │  Internal request (item needed)              │
    ├─────────────────────────────────────────────►│
    │                                              │
    │                              ┌─ In stock? ───┤
    │                              │               │
    │                    NO        │        YES    │
    │                              ▼               ▼
    │                 Procurement (PO)         Ship to branch
    │                 → Goods receipt          (goods issue)
    │                 → Stock in                 │
    │                              └──────┬───────┘
    │                                     │
    │◄──────────────────── Stock updated ─┘
```

**Key correction (locked):** branches place an **internal request** *before* the item is procured (if out of stock) or shipped (if in stock). This branch-side flow is **not built now** — it is the trigger for the procurement loop we build first.

### Price dynamics (locked — this is important)

| Value | Source | Update method |
|-------|--------|---------------|
| **Selling prices** (retail / wholesale / special) | `Item` | **Manual** — filled by a senior person, *not* automated |
| **Buying / cost price** | `SupplierItemPrice` (per supplier) | **Dynamic** — sourced from the supplier price list |

So "dynamically updated wherever possible" applies to **cost prices** and **stock**, not to selling prices.

---

## 3. Guiding principles

1. **One concept per phase.** No large application dumps.
2. **All mutations through `services.py`** — views/CLI/admin never touch models directly for writes.
3. **Audit-by-design** — every create/update/lifecycle change writes a `*ChangeLog` row with `user`, `action`, `changes`, `reason` (reuse the existing pattern).
4. **Plain Django + plain JavaScript.** No React/Vue, no extra frameworks.
5. **Normalized tables + joins** — the user's "separate tables + inner/outer joins" instinct is the house style; Django's `select_related` / `prefetch_related` implement the joins.
6. **~500 users, low traffic** → correctness and clarity over performance.
7. **PostgreSQL is the source of truth.** No client-side writes.
8. **Branch-readiness now, branches later** — keep `Item` global (no `branch_id`), stable PKs, snapshot prices onto future order lines, and expose cost only to warehouse groups (the future branch catalog will hide cost).

---

## 4. Naming conventions (locked)

| Concept | Name (code) | Notes |
|---|---|---|
| Catalog item (identity) | `Item` | exists |
| 3 selling prices | `Item.retail_price` / `Item.wholesale_price` / `Item.special_price` | manual, audited |
| Supplier cost price | `SupplierItemPrice` | supplier × item → `cost_price` |
| Purchase order | `PurchaseOrder` + `PurchaseOrderLine` | exists (Phase 2) |
| Receiving document | `GoodsReceipt` + `GoodsReceiptLine` | exists (Phase 3); "Receção de Mercadorias" (pt-PT) |
| Stock movement | `StockMovement` (ledger) + cached quantity on `Item` | exists (Phase 3) |
| Branch-side order | Internal request / "Requisição Interna" | future (Phase 5) |
| Discounts | `discount_commercial` / `discount_financial` / `rappel` | on PO lines, simple % |
| Manager view | Stock & price catalog (cost **visible**) | exists (Phase 4) |
| Branch view | Branch catalog (cost **hidden**) | future (Phase 5) |

---

## 5. Decisions log

### Locked ✅

| # | Decision | Choice |
|---|----------|--------|
| D1 | Selling prices are manual; cost is dynamic | Manual sell / dynamic cost (from supplier list) |
| D2 | 3 selling prices | retail, wholesale, special — **not** branch-tiered (buildable later) |
| D3 | Supplier cost price linkage | supplier ID + item (whose `internal_code` is written on the PO line) |
| D4 | Supplier price storage | separate table `SupplierItemPrice`, `unique(supplier, item)`, **no** supplier SKU / validity dates for now |
| D5 | Stock model | movement **ledger** + cached quantity on `Item` |
| D6 | Goods receipt ↔ PO | **many receipts per PO** (partial / split shipments) |
| D7 | Approval workflow | `draft → submitted → approved/rejected → received → closed`, plus **`cancelled`** (approved PO with zero receipts; required reason) |
| D8 | Rappel | simple per-line % now; shape later |
| D9 | Email automation | deferred to a **pending phase**; model a stub seam now |
| D10 | Branches | **not now**; only keep products branch-ready |
| D11 | `SupplierItemPrice.primary` semantics | preferred supplier for the item — auto-suggest on PO lines is a **later** enhancement; **always overridable** |
| D12 | PO line with no supplier price | **rejected** — no cross-supplier fallback |
| D13 | Approved totals snapshot | `approved_net` / `approved_vat` / `approved_gross` frozen at `approve()` |
| D14 | One primary supplier price per item | DB partial unique `unique_primary_supplier_item_price`; lock Item; clear other primaries before save |
| D15 | Duplicate PO lines | **rejected** (`unique_po_line_item`) — do not merge quantities |
| D16 | Inactive catalogue on POs / catalog | No PO create/submit/approve/add-line for inactive supplier or item; `get_catalog(active_only=True)` excludes inactive families; cannot assign items to an inactive family. Do **not** cascade-deactivate items when a family is deactivated |
| D17 | Warehouse groups | Code-owned `permissions.set()` on migrate; `assign_warehouse_group` is exclusive (one warehouse group) and resets grade to 1 |
| D18 | Warehouse grades + PO approval limits | Operator 1–2, manager 1–3; `ApprovalLimit` EUR gross; admin-only `/manage/approval-limits/`; operators never approve |
| D19 | PO/stock audit reasons + email stub | Required reason on reject, manual close, `adjust_stock`; `on_commit` around notify stub |
| D20 | Non-negative selling prices & reorder level | Finite and ≥ 0 (0 allowed); service validation + `MinValueValidator(0)` + DB `CheckConstraint`s |
| D21 | Family names immutable | Create-only; `name` not updatable; family PATCH does not rename |
| D22 | Supplier-item price activity | Only for an **active** supplier **and** item |
| D23 | VAT rate range | Fraction in `[0, 1]` (DB `CheckConstraint`) |
| D24 | PO line quantity bound | ≤ `1e9` (matches inventory) |
| D25 | Timezone validation | `User.clean()` (IANA); middleware `finally: deactivate()` |
| D26 | Dashboard permission list | Shown only to superusers / `DEBUG` |
| D27 | Login rate limiting | **Pre-production blocker** — deferred (`django-axes` or proxy) |
| D28 | Money rounding | `ROUND_HALF_UP` (half away from zero) via `procurement.models.round_money` — unit costs to 4 dp first, then monetary amounts to 2 dp |
| O1 | Item-level buying-price display | **Option A** — `primary` flag (one per item); fall back to cheapest if none marked — **implemented** |

### Open ⚠️

None. O1 was resolved as Option A (see locked table).

> **O1 options recap (historical):** A = primary supplier flag (chosen) · B = always show cheapest · C = per-supplier only, no single item-level cost.

---

## 6. Current state

**Live facts:** [`docs/handoff.md`](handoff.md). Do not use the list below as “today.”

**Current (Aug 2026):** phases 0–4 complete; both review backlogs cleared (2208 P0–P4, 1303 N1–N12) and archived; M7 console pagination done; **Phase 5 Slices 1–4 (tenancy + catalog + requisição + goods issue) done**; **368 tests green**. Remaining: Phase 5 slices 5–6 (branch receipt/stock → polish), Phase 6 (email), Phase 7 (mobile/offline/OAuth), and L13 (login rate limiting, production-only).

The following was the **Phase-0 snapshot** when this plan was first written (pre-pricing, pre-procurement, pre-stock). Kept as a record of the starting point:

- Apps then: `accounts`, `products`, `logging_utils`. No `branches` app (still true).
- `Item` then had no selling prices and no stock field.
- Tests then: 105 (`products` + `accounts`).

---

## 7. Phase map (overview)

| Phase | Name | Status | Depends on |
|-------|------|--------|------------|
| 0 | Catalogue identity + auth + console | ✅ **Done** | — |
| 1 | **Pricing — selling prices + supplier price list** | ✅ Done | Phase 0 |
| 2 | Procurement — purchase orders, discounts, approval | ✅ Done | Phase 1 |
| 3 | Goods receipt + stock ledger | ✅ Done | Phase 2 |
| 4 | Manager catalog (stock + price view) | ✅ Done | Phase 3 |
| 5 | Branches + internal request + branch catalog | 🔜 **In progress** — Slices 1–4 ✅; Slice 5 next | Phase 4 |
| 6 | Email automation (supplier notifications) | ⏸ Pending | Phase 2 (stub) |
| 7 | Mobile / offline / PWA / OAuth / deployment | ⏸ Future | Phase 5 |

---

## 8. Phase 1 — Pricing ✅

**Goal:** items carry 3 manually-entered selling prices; suppliers carry dynamic cost prices; the console lets warehouse staff manage both with full audit.

### 8.1 Data model

**`Item` — add 3 selling-price fields (manual, audited):**

| Field | Type | Notes |
|-------|------|-------|
| `retail_price` | `DecimalField(12,2)` | default `0.00` |
| `wholesale_price` | `DecimalField(12,2)` | default `0.00` |
| `special_price` | `DecimalField(12,2)` | default `0.00` |

- `0.00` means "not yet priced". Add to `ITEM_UPDATABLE_FIELDS` and to the item audit diff.
- *(Decision note: if branch/segment price tiering is later required, extract these into a `PriceList` model — do not do this now.)*

**`SupplierItemPrice` (dynamic cost source) — new:**

| Field | Type | Notes |
|-------|------|-------|
| `supplier` | FK → `Supplier`, `PROTECT` | `related_name="item_prices"` |
| `item` | FK → `Item`, `PROTECT` | `related_name="supplier_prices"` |
| `cost_price` | `DecimalField(12,2)` | ≥ 0 |
| `primary` | `BooleanField(default=False)` | O1 — one primary per item (enforced in service layer) |
| `created_at` / `updated_at` | `DateTimeField` | auto |

- `unique_together(supplier, item)` — one cost per supplier per item.

**`SupplierItemPriceChangeLog` — new (audit):**

| Field | Type |
|-------|------|
| `supplier_item_price` | FK, `PROTECT`, `related_name="change_logs"` |
| `user` | FK → `AUTH_USER_MODEL`, `SET_NULL`, nullable |
| `action` | choices: created / updated / deactivated / reactivated |
| `changes` | `JSONField(default=dict)` |
| `reason` | `CharField(blank=True)` |
| `created_at` | auto |

### 8.2 Service layer (`products/services.py`)

- Add `retail_price`, `wholesale_price`, `special_price` to `ITEM_UPDATABLE_FIELDS`; coerce `Decimal`; include in `create_item` / `update_item` diffs and the created-log.
- New functions (mirror supplier/family pattern):
  - `create_supplier_item_price(supplier, item, cost_price, primary=False, user=None)`
  - `update_supplier_item_price(...)` — diff + audit
  - `deactivate_supplier_item_price(...)` / `reactivate_supplier_item_price(...)` (if soft-delete added)
  - `set_primary_supplier_price(item, supplier_item_price, user=None)` — unset others, enforce one primary
  - `get_supplier_item_prices(item=None, supplier=None)` — with `select_related`
  - `get_supplier_item_price_history(...)`
  - `get_item_buying_price(item)` — primary's cost, else cheapest (O1)
- Validation: `cost_price >= 0`; duplicate `(supplier, item)` → clear error (reuse the `_save_*` + `IntegrityError` re-check pattern).
- New error classes: `DuplicateSupplierItemPriceError`, `InvalidCostPriceError`.

### 8.3 Permissions (`products/permissions.py`)

- Supplier-item prices follow the same warehouse-group rules as items/suppliers: `warehouse_admins` full, `warehouse_managers` add/change, `warehouse_data_operators` view.
- Selling prices ride the existing item add/change permissions (no new perm codes needed).

### 8.4 Django admin (`products/admin.py`)

- Add the 3 selling prices to `ItemAdmin` (fieldsets) + `ItemChangeLogInline` already diffs them.
- New `SupplierItemPriceAdmin` (inline under `SupplierAdmin`) + read-only `SupplierItemPriceChangeLogAdmin` (mirror existing change-log admins).

### 8.5 Console API (`products/console_views.py`)

- `_serialize_item` → include the 3 selling prices.
- New endpoints (authenticated warehouse groups):
  - `GET/POST /api/manage/supplier-prices/`
  - `GET/PATCH/DELETE /api/manage/supplier-prices/<id>/`
  - `GET /api/manage/supplier-prices/<id>/history/`
- `_console_payload` → include supplier-item-price lists (or lazy-load per drawer, matching the existing family/supplier drawer pattern).

### 8.6 Console UI (`item_console.html` + `console.js`)

- Item create/edit form → 3 selling-price inputs (numeric, EN + pt-PT labels).
- Supplier drawer → list of that supplier's item prices (item, internal_code, cost, primary) + add/edit cost + set-primary.
- Item drawer → list of that item's supplier prices (supplier, cost, primary).
- Follow existing patterns: `textContent`/`createElement` only (no `innerHTML`), `state.busy` double-submit guard, request-id guards on history loads, safe `localStorage` helpers.

### 8.7 Seed (`products/management/commands/seed_dev_data.py`)

- Add sample selling prices (retail > wholesale > special) and supplier-item cost prices for the seeded items/suppliers. **Idempotent** (case-insensitive lookups, `update_or_create`-style).

### 8.8 Tests (`products/tests.py`)

- Selling-price create/update + audit diff.
- `SupplierItemPrice`: create, duplicate rejected, cost ≥ 0, primary uniqueness, buying-price resolution (O1), audit log, permissions (admin/manager/operator), admin access, console API.

### 8.9 Docs pass

- Update `README.md` "Project status" + `AGENTS.md` to reflect: selling prices manual, `SupplierItemPrice` done, `branches` still deferred (correct the "done" claim), offline catalogue removed.

### Phase 1 — Definition of Done

§8 is the **build spec (done)**. Tracker in §15 is ticked.

- [x] Migrations clean; `migrate` runs on a fresh DB.
- [x] All mutations audited (selling-price changes on item; supplier-price create/update/lifecycle).
- [x] Console: enter/edit selling prices; manage supplier cost prices + primary from drawers.
- [x] `python manage.py test products accounts` green (new tests added, ≥ 105 baseline preserved).
- [x] Seed script idempotent with sample prices.

---

## 9. Phase 2 — Procurement (purchase orders) ✅

**Goal:** warehouse raises a PO to a supplier; lines auto-fill cost from `SupplierItemPrice` (editable); 3 discount types; approval workflow; email seam.

### Model (new `procurement` app)

- `PurchaseOrder`: `supplier` FK, `status` (`draft/submitted/approved/received/closed/rejected`), `created_by`, `approved_by`, `approved_at`, `supplier_ref` (optional), `notes`, timestamps. **Global** (central warehouse, no branch).
- `PurchaseOrderLine`: `purchase_order` FK, `item` FK, `description` (snapshot), `internal_code` (snapshot), `quantity` `Decimal(12,3)`, `unit_cost` (auto-filled from `SupplierItemPrice`, editable), `discount_commercial` `Decimal(5,2)`, `discount_financial` `Decimal(5,2)`, `rappel` `Decimal(5,2)`, `vat_rate` (snapshot), line totals.
- `PurchaseOrderChangeLog` (status + field audit) + `PurchaseOrderLineChangeLog` (or reuse a single PO audit capturing line diffs — decide at build).

### Service layer

- `create_purchase_order`, `add_line` (auto-fill cost from `SupplierItemPrice`; auto-suggest the item's **primary** supplier — overridable, D11), `update_line`, `submit`, `approve`, `reject`, `receive` (transition hook for Phase 3), `close`.
- Discounts: **commercial & financial & rappel as simple line %** (D8). Net line = `unit_cost × (1 − Σ discounts)`. Rappel treated as a plain % for now.
- Status transitions enforced (e.g. only `draft→submitted`, `submitted→approved/rejected`).
- Email seam: `notify_supplier_on_approval(po)` → **stub** that logs "would send" (D9).

### Console

- PO list + detail, line editor, discount fields, status buttons, permission-gated (warehouse admins create/approve; managers create; operators view).

### Definition of Done

- [x] PO with lines, auto-cost from supplier list, editable.
- [x] Approval workflow with audit.
- [x] Email stub present (no SMTP in dev).

---

## 10. Phase 3 — Goods receipt + stock ledger ✅

**Goal:** receiving goods writes stock; stock is a ledger, never typed on the product.

### Model

- `GoodsReceipt`: FK → `PurchaseOrder` (many receipts per PO, D6), `received_by`, `received_at`, `reference` (supplier delivery note / guia), notes.
- `GoodsReceiptLine`: FK → `PurchaseOrderLine`, `quantity_received` `Decimal(12,3)` (≤ remaining qty on PO line), optional over/under tolerance decision at build.
- `StockMovement`: `item` FK, `quantity` (signed: `+in / −out`), `movement_type` (`receipt`, `goods_issue`, `adjustment`), `reference` FK (polymorphic: receipt / order / adjustment), `created_by`, `created_at`.
- `Item.quantity` (cached balance) — updated transactionally with each `StockMovement`.

### Service layer (new `inventory` app, or `procurement` + helper in `products`)

- `receive_goods(po, lines)` → creates `GoodsReceipt` + lines, writes `StockMovement` (+in), updates `Item.quantity`, marks PO `received`/`closed` when fully received.
- `adjust_stock(item, qty, reason)` → manual adjustment (warehouse-admin only).
- Stock never written directly on `Item` — always via movement.

### Definition of Done

- [x] Goods receipt writes stock; ledger complete; partial receipts supported; PO closes when fully received.
- [x] Cached `Item.quantity` correct and never manually edited.

### Implementation notes (as built)

- New **`inventory` app**: `GoodsReceipt` + `GoodsReceiptLine` (unique per receipt+PO line), `StockMovement` (signed ledger with `GenericForeignKey` reference: receipt / future issue / adjustment), `Item.quantity` (cached, updated transactionally).
- `receive_goods(po, lines, user)` validates status (`approved`/`received`), rejects over-receipt (`qty > remaining`), creates receipt + movements, updates `Item.quantity`, then drives PO status `approved → received` (and `→ closed` when fully received) via the existing `procurement.services.receive`/`close`.
- `adjust_stock(item, qty, reason, user)` — manual adjustment, warehouse-admin only (`can_adjust_stock`).
- PO console "Receive" no-stock action removed; approved/received POs now link to `/manage/goods-receipts/?po=<id>`.
- Console at `/manage/goods-receipts/` (receipts list, new receipt, stock movements, adjust stock).

---

## 11. Phase 4 — Manager catalog (stock + price view) ✅

**Goal:** managers see a join-heavy, read-only view: item + 3 selling prices + buying price (O1) + stock balance + reorder level + supplier(s).

- Read-only dashboard joining `Item`, `SupplierItemPrice`, `StockMovement` (cached `quantity`), `Supplier`.
- Cost **visible** to warehouse groups only.
- Reorder-level highlighting (below reorder level → flag).

### Definition of Done

- [x] Dashboard (join view)
- [x] Reorder highlighting
- [x] Tests

### Implementation notes (as built)

- Service: `get_catalog()` (read-only `Item` join with `select_related` family/vat + `prefetch_related` supplier prices), `catalog_buying_price()` (O1 — primary else cheapest, from prefetched prices), `catalog_below_reorder()` (`reorder_level > 0 and quantity <= reorder_level`).
- API: `GET /api/manage/catalog/` → joined rows (quantity, reorder level, buying price, 3 selling prices, suppliers, `below_reorder` flag).
- UI: `/manage/catalog/` — read-only table with search, family filter, "below reorder only" toggle, and a warning row/pill for items at/below reorder. EN + pt-PT.
- Permission: view-only, gated by `catalog_required` (`products.view_item`) — warehouse groups only (cost hidden from branches is Phase 5).

---

## 12. Phase 5 — Branches + internal request 🔜

**Status:** decisions locked 21 Aug 2026 — see [`phase5-brainstorm-260821-1530.md`](phase5-brainstorm-260821-1530.md) §Locked decisions and [`phase5-roadmap-260821-1618.md`](phase5-roadmap-260821-1618.md). **Build spec authored:** [`phase5-plan-260821-1756.md`](phase5-plan-260821-1756.md) (+ proposed additions A–D, §13). **Slices 1–4 ✅ done** — tenancy (`branches` app), branch catalog (cost hidden, stock hint), requisição (internal request), and warehouse goods issue. **Next:** Slice 5 — branch receipt + branch stock.

- ✅ `branches` app: `Branch`, `BranchMembership` (`operator` / `manager` / `admin`), middleware, branch picker.
- ✅ Branch catalog: read-only (cost hidden, stock **hint** only).
- ✅ `orders` app: internal request ("Requisição interna") — priced (wholesale snapshot at approve); branch approve caps mirror PO.
- ✅ Warehouse: `GoodsIssue` + queue (approved requests only); partial issue + short-close; manual PO when out of stock (nullable PO FK on lines for later automation).
- Branch receipt + branch stock ledger (Slice 5) still to come.
- **Not in Phase 5:** offline/sync (Phase 7), email notify (Phase 6), stock reservation (deferred), linked/auto PO (later slice).

---

## 13. Phase 6 — Email automation (pending) ⏸

- Wire `notify_supplier_on_approval` to real email (SMTP / provider).
- Templates EN + pt-PT; audit sent-notifications.
- Deferred by D9.

---

## 14. Phase 7 — Mobile / offline / production (future) ⏸

- Offline catalogue cache (Service Worker + IndexedDB) — re-add after Phase 5.
- Offline order queue + idempotent sync.
- PWA manifest, HTTPS, Google OAuth, deployment.

---

## 15. Status tracker

> Tick `[x]` as tasks complete. Move `🔵 Current` in §7 forward each phase.

### Phase 1 — Pricing
- [x] 8.1 Models + migrations (Item prices, `SupplierItemPrice`, `SupplierItemPriceChangeLog`)
- [x] 8.2 Service layer (selling prices + supplier-price CRUD + primary + buying-price)
- [x] 8.3 Permissions
- [x] 8.4 Django admin
- [x] 8.5 Console API
- [x] 8.6 Console UI
- [x] 8.7 Seed data
- [x] 8.8 Tests
- [x] 8.9 Docs pass (fix branches/offline drift)

### Phase 2 — Procurement
- [x] Models + migrations
- [x] Service layer (PO, lines, discounts, approval)
- [x] Console UI
- [x] Email stub
- [x] Tests

### Phase 3 — Goods receipt + stock
- [x] Models + migrations
- [x] Service layer (receive → stock movement → cached quantity)
- [x] Console UI
- [x] Tests

### Phase 4 — Manager catalog
- [x] Dashboard (join view)
- [x] Reorder highlighting
- [x] Tests

### Phase 5 / 6 / 7
- [x] Phase 5 plan authored (`phase5-plan-260821-1756.md`)
- [ ] Phase 5 — branches + internal request (implementation; see roadmap slices)
  - [x] Slice 1 — tenancy (`branches` app, middleware, picker, admin, seed)
  - [x] Slice 2 — branch catalog (cost hidden, stock hint)
  - [x] Slice 3 — requisição (internal request)
  - [x] Slice 4 — goods issue
  - [ ] Slice 5 — branch receipt + branch stock
  - [ ] Slice 6 — polish + docs
- [ ] Phase 6 — email; Phase 7 — mobile/offline/OAuth (deferred)

---

## 16. Out of scope (explicitly not now)

- Branch app, internal request, branch catalog, branch tiered prices.
- Offline order queue / sync; PWA; mobile packaging.
- Google OAuth, public signup, password reset.
- Categories, LLM/vector search, bulk import.
- Real email sending.

---

## 17. Risks & notes

1. **Cost-price ambiguity (O1)** — resolved: Option A (`primary` flag).
2. **Docs drift** — live state is [`handoff.md`](handoff.md). `branches` and the offline catalogue are **not** in code.
3. **Rappel semantics** — simple % now may need rework if it becomes a true periodic accrual later.
4. **Stock concurrency** — ledger + `select_for_update()` (existing pattern) avoids lost updates on concurrent receipts; keep this discipline.
5. **Snapshot-on-line** — PO/GR lines must snapshot description, code, unit cost, VAT so later master-data edits don't rewrite history.
