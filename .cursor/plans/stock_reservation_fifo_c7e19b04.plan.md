---
name: Warehouse stock reservation (FIFO)
overview: "When a branch requisição is approved, reserve min(requested, unreserved on-hand) for that request so a later branch cannot take those units. Incoming stock auto-allocates FIFO to remaining backorders. Do not implement until this plan is accepted."
todos:
  - id: model-migration
    content: Add InternalRequestLine.quantity_reserved + CheckConstraint; data backfill allocate on existing approved/fulfilling lines
    status: pending
  - id: allocation-service
    content: "inventory.services allocate/release helpers; available_quantity(); lock items then lines; wire approve/cancel/issue/short-close/receive/adjust"
    status: pending
  - id: issue-guard
    content: issue_goods ships only from this line's reservation (run FIFO allocate first); new error strings
    status: pending
  - id: surfaces
    content: Manager catalog + item console + warehouse queue show on-hand / reserved / available; branch hint uses available
    status: pending
  - id: tests
    content: Partial reserve, later-branch cannot steal, FIFO on receipt/cancel, concurrent approve, adjust-below-reserved, issue/short-close release
    status: pending
  - id: docs
    content: "Manuals 03/04/05/07; PROJECT-PLAN D32; handoff; retire A4 deferred + parking-lot line"
    status: pending
isProject: false
---

# Warehouse stock reservation (FIFO partial claim)

**Status:** plan only — **do not code until this document is accepted.**

**Origin:** Phase 5 locked **A4 = no reservation** (check at goods issue). This plan **promotes A4** from deferred to a dedicated slice. It supersedes parking-lot A1 (“committed vs on-hand” visibility-only).

**Does not replace:** D5 (physical stock = `StockMovement` ledger + cached `Item.quantity`). Reservation is a **claim**, not a movement.

---

## 1. Problem (today)

```text
Stock on hand: 10 widgets

Branch North approves a requisição for 30
  → warehouse queue shows 30 remaining; Item.quantity still 10
Branch South then approves 10 (or warehouse issues 10 to South first)
  → South takes the 10; North is left with nothing on the shelf
```

`issue_goods()` row-locks items and rejects `qty > Item.quantity`, but **does not remember who asked first**. Two approved requests race at pick time. That is exactly the failure the user described.

Draft/submit do **not** appear on the warehouse queue; only **`approved` / `fulfilling`** do. Stock is not looked at on approve today.

---

## 2. Goal

When a requisição is **approved**, the warehouse **holds whatever is currently free** for that request. A later request cannot consume those units. If the first request asked for more than is free, the leftover is a **backorder**: it still occupies the queue, and **new stock is offered to it first** (FIFO), so North is not skipped when a PO is received.

Physical bins do not move until goods issue. `Item.quantity` stays “what is in the warehouse”.

---

## 3. Locked decisions (this slice)

**Recommendation (23 Aug 2026):** take **all twelve as written**. They are the unique set that fits today’s architecture (warehouse queue = `approved`/`fulfilling` only; D5 physical ledger; lock 3 no line status; lock 7 hint not exact qty; request-even-if-out-of-stock; short-close as the reasoned override). None is optional if the original “North keeps the 10” story must hold.

| ID | Topic | Choice | Rec |
|----|--------|--------|-----|
| R1 | **When to reserve** | At **branch approve** (`submitted → approved`). Not at draft, not at submit, not at add-line. | **Yes** |
| R2 | **How much** | `min(line remaining unissued, currently unreserved on-hand)` per item. Request is still approved if that is 0 (wait for procurement). | **Yes** |
| R3 | **Who wins** | **FIFO** on `(InternalRequest.approved_at, request.id, line.id)`. Same item, two branches: earlier approve gets free stock first. Same branch, two requests: same rule. | **Yes** |
| R4 | **Incoming stock** | After `receive_goods` / positive `adjust_stock`, **auto-allocate** free units to backorders in FIFO order (raise `quantity_reserved` up to remaining unissued). | **Yes** |
| R5 | **Release** | Cancel approved (0 issues), warehouse short-close remainder, and goods issue all **reduce reservation**. After a release that frees on-hand, immediately **re-allocate FIFO** so an older backorder beats a new approve. | **Yes** |
| R6 | **Issue** | May ship **only** from that line’s `quantity_reserved`. Before the check, run FIFO allocate for the items so leftover free stock is not sitting unclaimed. Warehouse cannot “pick South” while North still has a backorder and free stock exists — they must short-close/cancel North’s remainder first. | **Yes** |
| R7 | **Not a ledger type** | **No** `StockMovement.Type.RESERVE`. D5 unchanged: movements remain receipt / goods_issue / adjustment. | **Yes** |
| R8 | **Storage** | `InternalRequestLine.quantity_reserved` (`Decimal(12,3)`, default 0). Keep lock 3: **no line status enum**. Remaining issued/received stay derived. | **Yes** |
| R9 | **Available** | `available(item) = Item.quantity − sum(quantity_reserved)` over lines whose header is `approved` or `fulfilling`. Never negative (service invariant). | **Yes** |
| R10 | **Branch catalog hint** | Recompute lock 7 from **available**, not raw `Item.quantity`. Still **no exact qty** in branch UI. **None does not block raising a requisição** (already true today). | **Yes** |
| R11 | **Negative adjust** | `adjust_stock` **must not** take `Item.quantity` below total reserved. Shrink/damage: short-close or cancel claims first, then adjust. No silent haircut. | **Yes** |
| R12 | **Approve never fails on stock** | Lack of stock is not an approval error (caps, inactive item/branch, empty request, wholesale still apply). | **Yes** |

Proposed PROJECT-PLAN row when this ships: **D32 — Warehouse stock reservation** (R1–R12).

### 3.1 Why each lock (architecture)

**R1 — approve, not draft/submit.** The warehouse queue already ignores `draft`/`submitted`. Obligation starts when the branch manager approves (caps, wholesale snapshot, `approved_at`). Drafts can sit forever; reserving there would freeze bins for abandoned carts. Submit is still an internal branch step.

**R2 — only the free portion.** Phase 5 already allows a requisição when the hub is short (manual PO path). Holding the *full* 30 when 10 exist would starve every other branch of *future* receipts until North is fully shipped. Holding the 10 plus FIFO on new stock (R4) matches the user’s “available portion” wording without that starvation.

**R3 — FIFO by `approved_at`.** Same instant as R1. `created_at` / `submitted_at` would let a slow manager jump a branch that already approved. Tie-break `request.id`, then `line.id` is deterministic under row locks (M6).

**R4 — auto-allocate on receipt/adjust-up.** Without this, South can take units that arrive after North’s approve — the same race, one document later. `receive_goods` is the only stock-in path besides admin adjust; both must call the same allocate helper.

**R5 — release then re-allocate.** Cancel-approved and warehouse short-close already exist (reason required). If North drops the claim and we do *not* immediately offer those units to South, a brand-new East approve in the same second can steal them. Issue reduces reserved in lockstep with `Item.quantity` (available unchanged). Re-allocate only when a release **frees** on-hand (cancel / short-close remainder), not on a normal issue.

**R6 — issue only from that line’s reserved qty.** This is the enforcement of R2–R4. Letting pickers choose who gets free stock would make FIFO advisory. The existing override is **short-close / cancel with a reason** (D19/D31) — do not add a second “steal” button.

**R7 — no `RESERVE` movement.** D5: `Item.quantity` is the cached sum of `StockMovement`. A reserve movement would fake a stock-out, trip `item_quantity_gte_zero`, and confuse goods-receipt. Reservation is a claim beside the ledger.

**R8 — field on the line.** Lock 3: no line status; issued/received stay derived. Reserved **cannot** be derived (two requests both want 30, only 10 free — someone must be stored as holding it). `InternalRequestLine.quantity_reserved` is the smallest change. A separate reservation table is unnecessary at this scale.

**R9 — available = on-hand − reserved on `approved`+`fulfilling`.** Those are exactly the warehouse-queue statuses. Once `shipped`/`closed`/`cancelled`, reserved must be 0 (goods left, or claim released). Formula is the definition of “free to promise”, not a second cache on `Item`.

**R10 — hint from available.** Lock 7 already hides the exact number. Hinting from raw on-hand would show **In stock** while South cannot be shipped — the same lie that caused the bug. **None still does not block a requisição** (Phase 5: request *before* procurement). South should still approve and join the FIFO backorder. Manuals must say: None = nothing free to ship *today*, not “do not request”.

**R11 — adjust cannot go below reserved.** `adjust_stock` is already admin-only and reason-required. Silently cutting reserved would steal North’s claim with no requisição audit. Damage path: short-close/cancel the claim (reason), then adjust. Matches `item_quantity_gte_zero`: do not invent negative available.

**R12 — approve succeeds with zero stock.** If approve failed when available is 0, North could not even enter the queue, and the manual-PO loop would have no document to wait on. Stock shortage is a **fulfilment** problem (R2/R4), not an approval-cap problem (those stay).

---

## 4. Rejected alternatives

| Idea | Why not |
|------|---------|
| Reserve at **draft/submit** | Abandoned carts would freeze stock; warehouse is not obligated until approve. |
| Reserve the **full requested qty** even when on-hand is 0 (hard backorder of future receipts) | One huge North line would starve South until North is fully issued or short-closed. User asked to hold the **available portion**, not the whole future pipeline as an exclusive lock. FIFO on **incoming** stock still protects North’s remainder without blocking units North did not need. |
| Visibility-only “committed vs on-hand” (old A1) | Does not stop South’s issue from taking the last units. |
| Warehouse **chooses** who gets free stock at issue time | Re-opens the race; FIFO would be advisory. Override path = short-close/cancel (reason already required). |
| Write negative `StockMovement` on approve | Lies about physical stock; breaks `item_quantity_gte_zero` and goods-receipt mental model. |
| New `StockReservation` table | Useful if we later need a full allocate/release ledger; v1 changelog on the line is enough. Revisit if audit of every auto-allocate is required. |

---

## 5. Quantities (per line, per item)

```text
requested          = InternalRequestLine.quantity
issued             = sum(GoodsIssueLine.quantity_issued)     # derived
remaining          = requested − issued
reserved           = InternalRequestLine.quantity_reserved   # stored
backorder          = remaining − reserved                    # unfilled claim
on_hand            = Item.quantity                           # physical, D5
reserved_total     = sum(reserved) for approved+fulfilling lines of this item
available          = on_hand − reserved_total
```

**Invariants** (enforce in services; CheckConstraint where local):

1. `0 ≤ reserved ≤ remaining ≤ requested`
2. `sum(reserved for item) ≤ Item.quantity`
3. `available ≥ 0`
4. Header `shipped` / `received` / `closed` / `cancelled` / `rejected` / `draft` / `submitted` → all those lines have `reserved = 0`
5. Active reservation statuses: **`approved` and `fulfilling` only**

---

## 6. Scenario matrix

Assume one item unless noted. Quantities are widgets.

### 6.1 Core story (user)

| Step | On hand | North reserved / remaining | South reserved / remaining | Available |
|------|---------|----------------------------|----------------------------|-----------|
| Start | 10 | — | — | 10 |
| North approves 30 | 10 | 10 / 30 | — | 0 |
| South approves 10 | 10 | 10 / 30 | 0 / 10 | 0 |
| Warehouse tries to issue 10 to South | **reject** (South reserved 0) | | | |
| Warehouse issues 10 to North | 0 | 0 / 20 | 0 / 10 | 0 |
| PO receipt +15 | 15 | 15 / 20 | 0 / 10 | 0 |
| Issue 15 to North | 0 | 0 / 5 | 0 / 10 | 0 |
| PO receipt +20 | 20 | 5 / 5 | 10 / 10 | 5 |
| Issue rest to North then South | 5 then 0… | 0 | 0 | leftover 5 free |

North kept the original 10; incoming stock filled North’s backorder **before** South.

### 6.2 Enough stock for both

On hand 50. North 30 → reserved 30, available 20. South 10 → reserved 10, available 10. Either can be issued independently up to their reserved qty.

### 6.3 Zero stock at approve

On hand 0. North approves 30 → reserved 0, backorder 30. South approves 10 → reserved 0, backorder 10. Receipt +10 → North gets 10, South 0. Receipt +5 more → North 5 (if still 20 remaining) then South starts.

### 6.4 Cancel / short-close releases to older backorder

On hand 10. North 30 → reserved 10. South 5 → reserved 0. North **cancels** (0 issues) → North reserved 0; **re-allocate** → South reserved 5, available 5. A **new** third branch approving in the same second cannot jump South if allocation runs in the cancel transaction.

Warehouse **short-close** of North while `approved` (D31 → `closed`): same release + re-allocate. Short-close from `fulfilling`: release only **unissued** reserved remainder, then `shipped`; issued units already left via `GOODS_ISSUE`.

### 6.5 Partial issue then receipt

North 30, reserved 10; issue 6 → on hand 4, reserved 4, remaining 24, backorder 20. Receipt +20 → allocate 20 to North (reserved 24), available 0.

### 6.6 Concurrent approve of last units

Two transactions approve 10 each, on hand 10. Lock `Item` by pk (M6). One gets reserved 10, the other reserved 0. Both approved. `TransactionTestCase` like `ConcurrentIssueTests`.

### 6.7 Concurrent issue vs receive

`receive_goods` already locks items then writes movements. Allocation must **not** lock `InternalRequest` headers while holding item locks (deadlock with `issue_goods`, which locks the request first). Allocation locks **`InternalRequestLine` by pk** only. See §8.

### 6.8 Negative stock adjust

On hand 10, reserved 10. `adjust_stock(-1)` → **reject** with a dedicated error (exact string in manuals). Path for damage: short-close 1 unit of claim (or more), then adjust.

Positive adjust: same allocate path as goods receipt.

### 6.9 Multi-item request

North line A (widgets 30) and line B (tape 2). Reserve independently. Shortage of widgets does not block tape reservation.

### 6.10 Duplicate lines

Still **rejected** (`unique_request_line_item`). No merge.

### 6.11 Inactive item / branch (existing D16 / lock 9)

New work still blocked. **In-flight** approved/fulfilling keep snapshots **and** reservations so stock is not stuck. Issue / short-close / cancel still run.

### 6.12 Draft sitting while stock disappears

North draft 30, on hand 10; South approves 10 first → South reserved 10. North later approves → reserved 0. First **approved** wins, not first drafted.

### 6.13 Issue more than remaining

Unchanged: `InvalidIssuedQuantityError` (remaining requested). Reservation does not raise the requested qty.

### 6.14 Existing data at migrate

Open `approved`/`fulfilling` lines today have implicit reserved = 0. **Backfill** must run FIFO allocate once after the column exists; otherwise a **new** approve could take stock that an older open request was already waiting to pick.

---

## 7. Data model

On [`orders.InternalRequestLine`](orders/models.py):

- `quantity_reserved` — `Decimal(12, 3)`, default `0`
- `CheckConstraint` `quantity_reserved >= 0` (and `<= quantity` if we can express it without issued-qty, which is derived — so **≤ `quantity`** only)

No new app. No change to `StockMovement`. No `branch_id` on `Item`.

Changelog: `InternalRequestLineChangeLog` `UPDATED` when reserved changes (approve, allocate, issue, release), including `{quantity_reserved: {old, new}}`. Header status logs stay as today.

One `orders` migration + **data** step: `quantity_reserved=0` then call allocate per distinct `item_id` on open lines (or a service used by RunPython).

---

## 8. Services (all writes through `services.py`)

Put allocation in **`inventory/services.py`** (it already owns on-hand and `issue_goods`). `orders.services.approve` / `cancel` call into inventory inside the same `transaction.atomic`. Do not duplicate math in views.

### 8.1 Helpers

```text
available_quantity(item) -> Decimal
  # assumes caller holds Item row lock when using the result to write

allocate_available_stock(item, user=None)
  # Item already select_for_update
  # candidate lines: header in {approved, fulfilling}, remaining > reserved
  # order by request.approved_at, request_id, line_id
  # lock those InternalRequestLine rows by pk
  # while available > 0, raise reserved by min(available, backorder)

release_reservation(line, qty, user=None)
  # decrease reserved; then allocate_available_stock(item)
```

`approve`: after status/totals freeze, lock line items by **pk**, then for each line `allocate_available_stock` (or a “allocate this line from current available” that is the same FIFO function — **only this request’s new lines have reserved=0**, older lines already hold claims, so FIFO naturally fills the newly approved lines only if anything is left).

`cancel` from `approved`: release each line’s reserved (set 0) then allocate (other requests).

`issue_goods`: lock request (existing), lock items by pk (existing), **`allocate_available_stock` each item**, then require `qty <= line.quantity_reserved` (after refresh). Decrement reserved by `qty` (no re-allocate: on-hand and reserved fall together; available unchanged). Then `_write_movement(..., GOODS_ISSUE)` as today.

`short_close_issue`: release unissued reserved on all lines, allocate, then existing status transition (D31).

`receive_goods` / `adjust_stock`: after `_write_movement`, `allocate_available_stock` for touched items.

### 8.2 Lock order (deadlock)

| Procedure | Order |
|-----------|--------|
| `issue_goods` / `approve` / `cancel` / `short_close_issue` | Request header (already today) → **items by pk** → **lines by pk** |
| `receive_goods` / `adjust_stock` | Items by pk (already today) → **lines by pk only** (never the request header) |

Do not add `InternalRequest.select_for_update()` inside allocate-on-receipt.

### 8.3 Error strings (manuals §2)

Use these exact EN strings (pt-PT console i18n keys alongside):

| Code | EN |
|------|-----|
| `insufficient_reservation` | `Cannot issue {qty} of '{label}': {reserved} reserved for this request.` |
| `adjust_below_reserved` | `Cannot reduce stock of '{label}' below {reserved} reserved for approved requests.` |

Keep existing `InsufficientStockError` as a safety net if `qty > on_hand` (should be unreachable if invariants hold). Prefer the reservation error when `qty > reserved`.

Approve / submit messages unchanged.

---

## 9. Surfaces

| Surface | Change |
|---------|--------|
| `/manage/internal-requests/` queue + `get_issue_summary` | Per line: requested, issued, remaining, **reserved**, **backorder**, **on_hand**, **available**. Issue qty default ≤ reserved. |
| `/manage/catalog/` | Keep on-hand column; add **reserved** and **available**. “Below reorder” filter uses **available** vs `reorder_level`. |
| `/manage/items/` | Show on-hand as today; add available (read-only). Do **not** restyle the page beyond the extra figure. |
| `/branch/catalog/` | Hint from **available** (`none` if 0; `low` if `reorder_level > 0` and `available <= reorder_level`; else `in stock`). Still no exact number. |
| Branch requisição UI | Optional read-only “warehouse held / waiting” on **own** approved lines later; **not required** for v1 (warehouse queue is the operational screen). |
| `/` dashboard | No chrome restyle. |

Linked/auto PO (C1/C2) stays **out of scope**. Backorder on the queue is the signal for a **manual** PO.

---

## 10. Tests (plan these before coding)

Use `.venv/bin/python manage.py test … --noinput`. Prefer service tests; API tests for new payload fields.

- Partial reserve at approve (`30` requested, `10` on hand → reserved `10`)
- Second branch approve cannot raise reserved while available is 0
- Issue to second branch rejected (`insufficient_reservation`)
- Issue to first branch up to reserved succeeds; `Item.quantity` and reserved drop together
- Receipt allocates FIFO to the older backorder before the newer
- Cancel approved re-allocates to the waiting second request
- Short-close from `approved` releases; from `fulfilling` releases only unissued
- Concurrent double-approve of last unit: reserved sums to on-hand, never more (`TransactionTestCase`)
- `adjust_stock` negative below reserved rejected; positive allocate
- Invariants after issue: `available` unchanged
- Branch catalog hint `none` when on-hand > 0 but all reserved
- Backfill: two pre-existing approved requests + stock → older gets the units
- Existing tests that set `item.quantity` by hand after approve must go through services (today’s `test_cannot_issue_more_than_on_hand` will otherwise violate reserved > on-hand)

---

## 11. Docs (when implementing, not in this plan PR)

- [`docs/user-manuals/04-internal-requests.md`](docs/user-manuals/04-internal-requests.md) — approve holds stock; FIFO; short-close releases
- [`docs/user-manuals/03-goods-receipts.md`](docs/user-manuals/03-goods-receipts.md) — receipt fills backorders; adjust cannot go below reserved
- [`docs/user-manuals/07-manager-catalog.md`](docs/user-manuals/07-manager-catalog.md) — on-hand vs available
- [`docs/user-manuals/05-edge-cases-and-limits.md`](docs/user-manuals/05-edge-cases-and-limits.md) — new errors; retire “stock reservation deferred”
- [`docs/PROJECT-PLAN.md`](docs/PROJECT-PLAN.md) D32; tracker; Phase 5 “no reservation” wording
- [`docs/handoff.md`](docs/handoff.md), [`README.md`](README.md), [`AGENTS.md`](AGENTS.md) via session-handoff
- [`docs/future-enhancements-260821-1833.md`](docs/future-enhancements-260821-1833.md) — remove “Stock reservation — deferred (A4)”

Do **not** edit archived Phase 5 brainstorm/plan except to leave them archived.

---

## 12. Out of scope

- Phase 6 email, Phase 7 offline
- Auto / linked PO (nullable FKs stay unused)
- Branch-tiered prices, shared chrome, restyle `/`
- Reserving **branch** stock (this is warehouse hub stock only)
- Manual “steal this free stock for South” UI (use short-close)
- Changing D5 or adding `RESERVE` movements
- Exposing exact warehouse qty to branches

---

## 13. Implementation slices (after acceptance)

1. **Model + helpers + approve/cancel/issue/receive/adjust** + backfill + service tests (correctness first, UI can lag one commit if needed).
2. **Consoles + i18n + manuals** (queue, manager catalog, hint, item console).
3. **Handoff / PROJECT-PLAN D32.**

Do not mix Phase 6 email into this branch.

---

## 14. Acceptance checklist (product)

- North asks 30, hub has 10: those 10 cannot be issued to South.
- South can still **approve** a requisição (backorder); they wait for stock North does not still claim.
- After a PO receipt, North’s remaining 20 is reserved before South’s waiting qty.
- Cancelling or short-closing North returns units to the next FIFO waiter in the same transaction.
- Manager catalog can explain “10 on hand, 10 reserved, 0 available”.
- Branch catalog says **None** when everything on the shelf is already held.

---

## 15. How to object (before coding)

**Default:** accept R1–R12 as written (§3.1). Reply with a lock id only to override.

Forks that **break** the original North-keeps-the-10 story (do not take these):

- **R4 off:** later approve/issue can snatch PO receipts.
- **R6 off:** pickers can ignore FIFO.
- **R5 off:** cancel/short-close leaves a gap a newer branch can steal.
- **R12 off:** empty hub cannot raise a waiting requisição (contradicts Phase 5).

Milder forks (not recommended):

- **R1:** reserve at submit — freezes stock before the warehouse is obligated.
- **R2:** hard-reserve the full requested qty including future receipts — starves other branches.
- **R10:** keep hinting from raw on-hand — branch UI would show In stock when nothing is free.
