> **✅ COMPLETE — Phase 5 shipped 21 Aug 2026 (Slices 1–6). This document is ARCHIVED.**
> See `docs/handoff.md` for current state and next steps. (Archived to `docs/archive/` 21 Aug 2026.)

# Phase 5 — Branches + Internal Request — Brainstorm

> **Draft for discussion.** Created 21 Aug 2026, 15:30 WEST.  
> **Ambiguities A1–B8 locked** 21 Aug 2026 — see §Locked decisions below.  
> **Do not implement from this doc yet** — follow [`phase5-roadmap-260821-1618.md`](phase5-roadmap-260821-1618.md) Step 1 for formal plan, then slices.  
> Sources: all project `.md` files, Phases 0–4 code (`products`, `procurement`, `inventory`, `accounts`).

---

## Locked decisions (21 Aug 2026)

### Roles & approval (A1, A2, B3)

- **`operator`, `manager`, `admin`** on `BranchMembership` — not `user`.
- **Manager** = operator permissions + approve/reject; **admin** = + memberships, overrides, branch stock adjust.
- **No `branch_grade`** for MVP — operator always mutates.
- Branch accounts provisioned by **warehouse admin / superuser** (`/admin/`) for now.
- **Self-approve:** managers may approve own submission; **dual EUR gross caps** (self vs others), mirror PO `ApprovalLimit`; admin unlimited; operator never approves.

### Pricing (A3)

- Requests are **priced** — not quantity-only forever.
- Snapshot **`wholesale_price`** + VAT on each line at **approve**; reuse `round_money`.
- Branch UI may **hide totals initially**; model/services carry money from day one.
- No branch-tiered prices for MVP (D2 unchanged).

### Stock & fulfilment (A4–A10, A6–A9)

- **No warehouse stock reservation** for MVP — check at goods issue with row locks; reservation deferred.
- **Manual PO** when out of stock for MVP; schema includes **line fulfilment state + nullable PO/PO-line FK** for linked/auto PO later.
- **Branch stock:** ledger + cached qty per `(branch, item)` — mirror warehouse.
- **`GoodsIssue` + lines** in `inventory` — mirror `GoodsReceipt`; `GOODS_ISSUE` movements.
- **Partial ship** OK; short-close with **reason** (PO pattern).
- Branch receipt **rejects** qty > shipped remaining; fix via new issue or admin branch adjust + reason.
- Branch catalog: **availability hint only** (in stock / low / none) — no exact warehouse qty.

### Scope & workflow (B1, B2, B4, B5, B6, B7, B8)

- **Offline/sync → Phase 7** only; Phase 5 is online branch flows.
- App code: `orders` or `requests`; UI: **Requisição interna** — avoid “order” in branch UI (PO owns that term).
- **Multi-branch users** supported; **active branch** in session + picker.
- Warehouse queue: **`approved`** requests only — not at `submitted`.
- **Inactive items:** block on new lines (D16); in-flight lines keep snapshots if item deactivated later.
- **No notifications** in Phase 5; `on_commit` stubs in Phase 6 when email lands.
- **Cancel:** draft — operator/manager; `submitted` — manager **reject**; `approved` pre-ship — cancel with reason (manager/admin); **no cancel after partial goods issue** — short-close only.

---

## 1. What exists today (ground truth)

- **Central warehouse loop is complete:** catalogue → supplier prices → PO → goods receipt → `StockMovement` ledger → cached `Item.quantity`.
- **Global catalogue:** `Item` has no `branch_id`; selling prices are manual (retail / wholesale / special); cost is dynamic from `SupplierItemPrice`.
- **Stock in:** many `GoodsReceipt`s per PO; partial receipts OK; over-receipt rejected; PO auto-closes when fully received.
- **Stock out hook exists but unused:** `StockMovement.Type.GOODS_ISSUE` — documented in user manual as “future: shipping to a branch”.
- **Warehouse auth:** Django groups (`warehouse_admins` / `warehouse_managers` / `warehouse_data_operators`) + `warehouse_grade` + `ApprovalLimit` (EUR gross caps on PO approve).
- **Branch auth:** **not built.** No `branches/` app, no `BranchMembership`, no `request.active_branch`, no branch users in seed.
- **294 tests green** across `products`, `accounts`, `procurement`, `inventory`.

---

## 2. Business vision (end-to-end)

```text
Branch user                         Central warehouse
    │                                      │
    │  Internal request (Requisição)       │
    ├─────────────────────────────────────►│  request appears in warehouse queue
    │                                      │
    │                              ┌─ Item in stock? ─┐
    │                              │                  │
    │                     NO       ▼           YES    ▼
    │                   Raise PO → receive    Goods issue (−stock)
    │                   → stock in            (ship / dispatch)
    │                              └──────────┬───────┘
    │                                         │
    │◄──────────── physical delivery ─────────┘
    │
    │  Branch goods receipt (+stock at branch)
    └─ branch stock ledger updated
```

- **Internal request** = branch asks the hub for catalogue items (not a supplier PO).
- **Warehouse fulfils** by decrementing central stock (`goods_issue`) and recording what was sent.
- **Branch confirms arrival** with its own receipt document (mirror of warehouse GR, but scoped to branch).
- **Out-of-stock path:** procurement loop already exists; the open question is *who* triggers PO creation and *how* the branch request stays linked while waiting.

---

## 3. Proposed app split

| App | Responsibility | Rationale |
|-----|----------------|-----------|
| **`branches`** | `Branch`, `BranchMembership`, active-branch session/middleware, branch user admin, branch-scoped permissions | Tenancy foundation; no order business logic |
| **`orders`** (or `requests`) | Internal request header + lines, status workflow, audit logs, branch console API | Mirrors `procurement` pattern; every row has `branch_id` |
| **`branch_inventory`** (name TBD) | Branch-side receipt + branch stock ledger + cached branch quantity | Mirrors `inventory` but tenant-scoped; keeps warehouse ledger separate |

- **Keep `Item` global** — branches never edit master catalogue (locked in handoff + tenancy doc).
- **Do not copy tenancy-doc §6–7** — real lines reference `Item` with snapshots (description, code, UoM, price, VAT), like PO lines.
- **Reuse patterns:** `services.py` for all writes, `*ChangeLog`, `select_for_update()`, snapshot fields, EN + pt-PT, plain JS console.

---

## 4. Branch roles — map to your “operator + manager” idea

### Tenancy doc (3 roles)

| Role | Create request | Edit/delete request | Manage branch users |
|------|:---:|:---:|:---:|
| Admin | ✅ | ✅ | ✅ |
| Manager | ✅ | ❌ | ❌ |
| User | ✅ | ❌ | ❌ |

### Your stated minimum (2 users per branch)

- **Data operator** — does the legwork (build draft, add lines, submit).
- **Manager** — approves (or does both legwork and approval).

### Proposed mapping (for discussion)

| Your role | Likely maps to | Notes |
|-----------|----------------|-------|
| Data operator | `user` (tenancy doc) or new `operator` enum | Can draft + submit; cannot approve |
| Manager | `manager` | Can draft + submit + **approve** |
| Branch admin | `admin` | Optional third role — manages branch memberships; may or may not approve |

- **Warehouse parallel:** operator grade 1 = view-only; grade 2 = mutate; manager grade 2+ = approve with caps; admin = unlimited.
- **Branch may need its own grade or approval caps** — not decided yet (see ambiguities §13).

---

## 5. Internal request — document & lines (sketch)

### Header (`InternalRequest` / `BranchRequest` — name TBD)

- `branch` FK (required, PROTECT)
- `status` — propose mirroring PO: `draft → submitted → approved/rejected → … → closed/cancelled`
- `created_by`, `submitted_by`, `approved_by`, timestamps
- `approved_*` monetary snapshot? — **only if branch requests are priced** (see §8)
- `notes`, optional delivery reference
- `warehouse_notes` — visible to warehouse staff only?

### Lines (`InternalRequestLine`)

- `internal_request` FK
- `item` FK (PROTECT)
- **Snapshots** (like PO): `description`, `internal_code`, `unit_of_measure`, `quantity`, `unit_price`?, `vat_rate`
- `unique(request, item)` — same rule as PO (no duplicate lines; do not merge qty)
- Quantity bound ≤ `1e9`, 3 dp — match inventory

### Status workflow (first draft)

| Status | Meaning | Who acts |
|--------|---------|----------|
| `draft` | Branch user building cart | operator/manager |
| `submitted` | Waiting branch approval | manager |
| `approved` | Branch approved; visible to warehouse | manager (or self-approve if same person?) |
| `rejected` | Branch rejected | manager |
| `fulfilling` | Warehouse picking / partial ship | warehouse staff |
| `shipped` | All lines fully issued (or short-closed) | warehouse |
| `received` | Branch confirmed at least partial receipt | branch |
| `closed` | Fully received at branch (or short-closed with reason) | system / manager |
| `cancelled` | Cancelled before ship | branch admin? manager? |

- Exact transitions need locking — PO pattern is the template (`procurement/services.py` `_transition`).

---

## 6. Branch-side workflow (UX)

### Catalog browse (read-only)

- Reuse `get_catalog(active_only=True)` — hide inactive families/items.
- **Hide cost** (`SupplierItemPrice`, buying price) — locked for Phase 5 branch view.
- **Show:** description, code, family, UoM, stock-at-warehouse? (see ambiguity), selling price(s), VAT label.
- Mobile-friendly layout deferred to Phase 7, but URLs should not assume desktop-only.

### Create request

- Pick items from catalog → lines with quantities.
- Validate: active item only; qty > 0; no duplicate lines.
- Save as `draft`.

### Submit & approve (branch)

- **Submit:** at least one line; moves to `submitted`.
- **Approve:** manager role (or admin); optional EUR cap / self-approval rule — TBD.
- **Reject:** reason required (mirror PO reject).
- **Edit/delete lines:** draft only; after submit → locked (mirror PO).

### After warehouse ships

- Branch user opens “pending deliveries” → records **branch goods receipt**.
- Partial receipts allowed (mirror warehouse GR).
- When all lines fully received → `closed`.

---

## 7. Warehouse-side workflow (fulfilment)

### Request queue (new console?)

- List `approved` internal requests (all branches or filter by branch).
- Show lines with **central stock available** vs **requested** vs **already issued** vs **remaining**.

### In stock — goods issue

- New service: `issue_goods(internal_request, lines, user, reference="", notes="")`
  - Creates `GoodsIssue` document (mirror `GoodsReceipt`).
  - Writes `StockMovement` **negative** qty, type `GOODS_ISSUE`, linked via `GenericForeignKey`.
  - Decrements `Item.quantity` (same `_write_movement` pattern in `inventory/services.py`).
  - Validates: cannot issue more than request remaining; cannot issue more than warehouse on-hand.
- Partial issues per request line — mirror partial GR.
- Multiple issues per request — mirror many GRs per PO.

### Out of stock — procurement link

- **Option A — manual:** warehouse staff sees “insufficient stock”, creates PO separately (today’s console); request stays `approved` until stock exists; no automatic link.
- **Option B — linked:** request line flagged `awaiting_stock`; optional “create PO from request” action aggregates lines across requests; PO carries back-reference.
- **Option C — auto PO:** system creates draft PO for primary supplier — high automation, more rules needed.

- **Recommendation for MVP:** Option A or B; avoid Option C in first slice.

### Who does warehouse fulfilment?

- Same warehouse groups that can `receive_goods` today (`can_mutate_catalog`) — likely managers + admins, operator grade 2+.
- Separate permission `can_issue_goods`? — cleaner than overloading receipt perm.

---

## 8. Pricing on internal requests

### Locked today (D1, D2)

- Three **manual** selling prices on `Item`; **not** branch-tiered.
- Cost is **hidden** from branch catalog.

### Open questions

- Which selling price applies to a branch request line?
  - Always `wholesale_price`?
  - Per-branch config (`Branch.default_price_tier`)?
  - Branch manager picks tier per request?
- Are internal requests **financial documents** (net/VAT/gross, approval caps) or **quantity-only requisitions**?
  - If quantity-only → simpler branch approve; warehouse sees qty only.
  - If priced → snapshot at approve like PO; branch `ApprovalLimit` analogue.

---

## 9. Branch goods receipt & branch stock

### Why a separate ledger

- Central `Item.quantity` = warehouse on-hand only.
- Branch needs its own balance per item per branch (or per branch aggregate, not per user).
- Branch receipt confirms **what physically arrived**; may differ from shipped qty (damage, short shipment).

### Proposed models (mirror warehouse)

| Warehouse | Branch analogue |
|-----------|-----------------|
| `GoodsReceipt` + `GoodsReceiptLine` (vs PO) | `BranchReceipt` + `BranchReceiptLine` (vs internal request / goods issue) |
| `StockMovement` on global `Item` | `BranchStockMovement` on `(branch, item)` with cached `BranchItemStock.quantity` |
| `receive_goods()` | `receive_at_branch()` |
| `adjust_stock()` | `adjust_branch_stock()` — branch admin only? |

### Linking documents

- **Goods issue (warehouse)** → **branch receipt** should reference same request line.
- Receipt validates: `qty_received ≤ qty_shipped − qty_already_received_at_branch`.
- Over-receipt at branch: reject (same as warehouse GR) or allow with manager reason?

### Movement types at branch

- `receipt` — from internal request fulfilment
- `adjustment` — stock count / damage
- `issue`? — if branch ever consumes stock locally (future; out of scope?)

---

## 10. Tenancy & security

### Branch isolation

- Every query on requests/receipts/branch stock: filter by `branch_id`.
- QuerySet helpers: `.for_branch(branch)`, `.for_user_branches(user)` — from tenancy doc §6.
- Middleware: `request.active_branch` from session; picker when user has 2+ memberships.

### User ↔ warehouse ↔ branch

- Same `accounts.User` can be:
  - warehouse-only (current seed users),
  - branch-only (no warehouse groups),
  - both (regional role — rare but supported by separate permission systems).
- **Warehouse groups must not grant branch access** and vice versa (tenancy doc § intro).

### Branch membership provisioning

- Phase 5 MVP: superuser creates branches + memberships in `/admin/`, or warehouse admin console — TBD.
- No public signup (consistent with auth plan).

---

## 11. UI / URL sketch (plain Django + JS)

| URL | Audience | Purpose |
|-----|----------|---------|
| `/branch/select/` | branch user | Active branch picker |
| `/branch/catalog/` | branch user | Read-only catalog (no cost) |
| `/branch/requests/` | branch user | Internal request list + editor |
| `/branch/receipts/` | branch user | Branch goods receipt |
| `/manage/internal-requests/` | warehouse | Fulfilment queue + goods issue |
| `/api/branch/...` | branch JSON API | Same shapes as warehouse consoles |

- **Shared chrome / navigation** explicitly deferred — each console may stay standalone initially (handoff: do not restyle `/` in passing).
- Reuse console patterns: drawers, busy flag, `_parse_decimal`, pagination (`?page=` already on warehouse APIs — M7 done).

---

## 12. Audit & logging

- `InternalRequestChangeLog`, `InternalRequestLineChangeLog` — mirror PO logs.
- `GoodsIssueChangeLog` — warehouse side.
- `BranchReceiptChangeLog`, `BranchStockMovement` — branch side.
- Required reasons: reject, cancel, short-close, branch stock adjust (mirror D19).
- Logger names: `centcompras.orders`, `centcompras.branch_inventory` (or nested under `branches`).

---

## 13. Ambiguities & doc drift (please resolve)

### High impact (blocks design)

| # | Topic | Conflict / gap |
|---|--------|----------------|
| A1 | **Branch roles** | Tenancy doc: admin / manager / **user**. You: **operator + manager** (min 2). Is branch `admin` required? Rename `user` → `operator`? |
| A2 | **Self-approval** | You: “manager can do legwork and approve.” Allow approve on own submission? Warehouse PO has self-approval **limits** (`SelfApprovalLimitError`). Same for branch? |
| A3 | **Pricing on requests** | D2: not branch-tiered. PROJECT-PLAN §12: “possibly branch-tiered — revisit.” Are requests priced at all? Which of the 3 sell prices? |
| A4 | **Stock reservation** | When branch request is `approved`, is warehouse stock **reserved** or only checked at issue time? Affects concurrent requests for last units. |
| A5 | **Out-of-stock path** | Manual PO vs linked PO vs auto PO — who tracks the wait state on the request line? |
| A6 | **Branch stock model** | Separate `BranchItemStock` table vs stock only on receipt history (no cached qty). Cached qty strongly recommended (mirror warehouse D5). |
| A7 | **Goods issue document** | New `GoodsIssue` model in `inventory` vs fulfilment fields on request — needs a first-class document like GR for audit. |
| A8 | **Partial / short ship** | If warehouse ships less than approved, can branch close request with remaining? Reason required? Mirror PO manual close? |
| A9 | **Branch receipt vs ship qty** | If branch receives **more** than shipped (data entry error), reject or adjustment workflow? |
| A10 | **Show warehouse stock to branch?** | Catalog shows central `Item.quantity` or hide to avoid gaming / confusion? |

### Medium impact

| # | Topic | Conflict / gap |
|---|--------|----------------|
| B1 | **Phase 5 vs 7 scope** | PROJECT-PLAN §12 lists “Offline order queue + sync” under Phase 5; §14 puts offline sync in Phase 7. Which phase owns offline? |
| B2 | **App naming** | `orders` vs `requests` vs `internal_requests` — “Order” overloaded with PO in users’ minds. Prefer **Requisição Interna** in UI. |
| B3 | **Branch admin role** | Tenancy doc: only admin can edit/delete others’ requests. Needed if manager is sole power user? |
| B4 | **Cross-branch user** | Picker + separate data per branch — confirm UX for regional manager. |
| B5 | **Warehouse visibility** | Can warehouse see branch request **before** branch approves (`submitted` only vs `approved`)? Recommend: warehouse sees only `approved+`. |
| B6 | **Inactive items** | Same rule as PO (D16): block add line on inactive item/family on new requests; what about in-flight requests when item deactivated? |
| B7 | **Email / notify** | Notify warehouse when branch approves? Notify branch when shipped? Phase 6 stub pattern? |
| B8 | **Cancel policy** | Can branch cancel after warehouse started picking? After partial issue? |

### Doc drift (not blocking code, but confusing)

| # | Topic | Detail |
|---|--------|--------|
| C1 | PO approve in user manual | [`02-purchase-orders.md`](user-manuals/02-purchase-orders.md) says approve is **admin only**; code + handoff: **manager grade 2+** within caps. Manual is stale. |
| C2 | Old plan files | `.cursor/plans/auth_and_tenancy_foundation_*.plan.md` marks branches app **completed** — **incorrect** vs live repo (no `branches/` directory). |
| C3 | Security audit plan | References `branches/middleware.py` and `/api/products/` — offline catalogue removed; branches not built. |
| C4 | README test count | README says “~264 tests”; handoff says **294**. |

---

## 14. Suggested build slices (after decisions locked)

### Slice 0 — Plan sign-off

- Resolve ambiguities §13 (at least A1–A7).
- Write formal `docs/phase5-plan-*.md` with locked transitions + ERD.

### Slice 1 — Tenancy foundation

- `branches` app: `Branch`, `BranchMembership`, permissions, admin, middleware, picker, seed sample branches + users.
- Tests: isolation, picker, 0/1/N memberships.

### Slice 2 — Branch catalog (read-only)

- `/branch/catalog/` + API; cost hidden; reuse `get_catalog`.
- Tests: branch user cannot hit `/manage/*`; warehouse user cannot hit branch APIs without membership.

### Slice 3 — Internal request (branch only)

- Models + services + branch console: draft → submit → approve/reject.
- No warehouse fulfilment yet; status stops at `approved`.

### Slice 4 — Warehouse goods issue

- `GoodsIssue` + `issue_goods()` + warehouse console queue.
- `StockMovement.Type.GOODS_ISSUE` live; central stock decrements.
- Request status → `fulfilling` / `shipped`.

### Slice 5 — Branch goods receipt + branch stock

- Branch receipt console + branch stock ledger + cached branch quantity.
- Request → `received` / `closed`.

### Slice 6 — Procurement link (optional MVP+)

- “Awaiting stock” flag + manual or semi-automated PO linkage.

### Explicitly later (Phase 7)

- Offline catalogue cache, offline request queue, idempotent sync, PWA, OAuth.

---

## 15. Patterns to copy from existing code

| Pattern | Where | Apply to Phase 5 |
|---------|-------|------------------|
| Status machine + `_transition` | `procurement/services.py` | Internal request workflow |
| Approved totals snapshot | `PurchaseOrder.approved_*` | If requests are priced |
| `_lock_po` / `select_for_update` | procurement + inventory | Lock request + items on issue/receipt |
| Duplicate line rejection | `unique_po_line_item` | `unique_request_line_item` |
| Partial receipt + remaining map | `inventory/services._received_qty_map` | Issue map + branch receipt map |
| `_write_movement` signed ledger | `inventory/services.py` | Warehouse issue; branch receipt |
| Capabilities module | `accounts/capabilities.py` | `branches/capabilities.py` for branch roles |
| Change logs with JSON diffs | all apps | All new mutable entities |
| `round_money` / D28 | `procurement/models.py` | If request lines have money |
| Inactive entity guards | `InactiveItemError` etc. | Request line add/submit/approve |
| Seed idempotency | `seed_dev_data.sh` | Sample branches + branch users |

---

## 16. Seed & dev testing (proposal)

- 2 branches: e.g. `Branch North`, `Branch South`.
- Per branch: `operator@north.dev`, `manager@north.dev` (+ optional `admin@north.dev`).
- Password `devpass123`; **no** warehouse groups on branch users.
- One user with memberships on **both** branches (test picker).
- Sample internal request in `draft` and one `approved` waiting fulfilment.

---

## 17. Tests worth planning upfront

- Tenant isolation: user A cannot read branch B’s request (404, not 403 leak).
- Cannot issue more than warehouse stock; concurrent issues on last unit.
- Cannot branch-receive more than shipped remaining.
- Status transition guards (no skip `draft → shipped`).
- Inactive item blocked on new lines; snapshot preserved on old lines.
- Branch catalog API never exposes `cost_price` / supplier prices.
- Manager-only approve; operator cannot approve.
- Self-approval rule once A2 decided.

---

## 18. Clarifying questions for you

1. **Roles:** For minimum 2 users per branch, do you want exactly **`operator` + `manager`**, or keep **`admin`** as a third (membership management)? Should we rename tenancy-doc `user` → `operator`?
2. **Self-approval:** Can the same person submit and approve a request? Always, never, or only with a cap / second pair of eyes above a threshold?
3. **Money on requests:** Are internal requests **quantity-only requisitions**, or do they carry **prices and totals** visible to the branch manager (and approval caps in EUR)?
4. **Selling price tier:** If priced, which price applies — fixed wholesale, per-branch default, or selectable per request?
5. **Warehouse stock visibility:** Should branch catalog show **how much the hub has in stock**, or hide it?
6. **Stock reservation:** When a request is approved, should quantities be **reserved** at the warehouse until issued or cancelled?
7. **Out of stock:** When hub lacks stock, is it enough for warehouse staff to **manually create a PO** (no system link), or do you want the request **linked/aggregated** into procurement?
8. **Partial shipments:** Are partial hub shipments and partial branch receipts **expected in normal operations** (like PO/GR today)?
9. **Branch receipt discrepancies:** If branch receives **less** than shipped, does the request stay open for the remainder, or close with reason? If **more** (error), hard reject?
10. **Warehouse queue:** Should warehouse see requests as soon as branch **submits**, or only after branch **approves**?
11. **Cancel:** Until which point can branch cancel — draft only, before ship, after partial ship?
12. **Phase 5 scope:** Confirm offline/sync is **Phase 7**, not Phase 5 (despite PROJECT-PLAN §12 bullet).
13. **Branch stock adjustments:** Who can adjust branch stock counts — branch manager, branch admin, or warehouse admin only?
14. **Naming:** Preferred UI term — **Internal request**, **Requisição interna**, or something else?

---

## 19. Recommended default stance (if we need to move before all answers)

- **Roles:** `operator` + `manager` + optional `admin`; operator submits, manager approves; admin manages users.
- **Self-approval:** allowed for manager **under a EUR gross cap**; stricter cap for self vs others (mirror PO `ApprovalLimit` pattern, separate table scoped to branch roles).
- **Pricing:** quantity-only for MVP slice 3–5; add price snapshots in a later slice if needed.
- **Warehouse stock:** show **availability hint** (“in stock” / “low” / “unavailable”), not exact qty — reduces contention and gaming.
- **Reservation:** no reservation in MVP; check at issue time with row locks.
- **Out of stock:** manual PO; request line stays `approved` with warehouse note “awaiting stock”; no auto PO.
- **Partial ship/receive:** yes, mirror PO/GR.
- **Warehouse queue:** only **`approved`** requests.
- **Offline:** Phase 7 only.

---

## 20. Next step after this brainstorm

- Your answers to §18 (even partial).
- Reorganise this doc into a **locked plan** (`docs/phase5-plan-YYYYMMDD-HHMM.md`).
- Update `PROJECT-PLAN.md` §12 + status tracker **only after you approve** (per your instruction: no existing file edits without approval).
