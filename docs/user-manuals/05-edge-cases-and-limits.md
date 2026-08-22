# CentCompras — User Manual: Edge cases, limits & troubleshooting

**Reference** · Version 1.0 · For warehouse staff, branch staff, and administrators

> **Companion to:** [Item Console](01-items.md) · [Purchase Orders](02-purchase-orders.md) · [Goods receipt & stock](03-goods-receipts.md) · [Branches & Requisição interna](04-internal-requests.md) · [Admin & Superuser Reference](06-admin-reference.md) · [Manager catalog](07-manager-catalog.md).
>
> Those manuals teach the normal path. **This one is the lookup reference** for the boundaries: the exact errors you can hit, the hard numeric limits, the state-machine rules, and the things that are *deliberately not built yet*. When something "won't let you", look here.

---

## 1. How to use this manual

- **"I got an error message"** → §2, find the message, read the fix.
- **"Is there a limit on …?"** → §3 (numeric limits table).
- **"Why can't I move it from A to B?"** → §4 (state machines).
- **"Why did my number round like that?"** → §5 (money & VAT).
- **"Can two people overwrite each other?"** → §6 (concurrency & audit).
- **"Is X built yet?"** → §7 (known gaps).

A message that "won't let you" is the app **protecting the ledger** — not a bug.

---

## 2. Error messages & what they mean

### 2.1 Catalogue (item console — `/manage/items/`)

| Message (exact) | Why it appears | What to do |
|-----------------|----------------|------------|
| `Internal code "X" is already used by another item.` | Internal codes are unique, **case-insensitive** | Use a different code |
| `Internal code may only contain letters, digits, dots, hyphens, and underscores.` | The code contains a **space** or a **disallowed character** (only `A–Z`, `a–z`, `0–9`, `.`, `-`, `_` are allowed) | Fix the code (e.g. `CEM-50`, `CABLE-2.5`) |
| `Internal code cannot be changed after the item is saved.` | You tried to rename a code on an existing item | Codes are locked after first save (legacy empty codes may be set once) |
| `Item cannot be activated (Genesis): missing …` | First activation (Genesis) needs internal code, description, unit, VAT, active family, and **retail price > 0** (console save, Django admin **Reactivate** bulk action, or `add_item --activate`) | Complete the fields before activating |
| `Family name "X" is already used.` | Family names are unique, case-insensitive | Use another name |
| `Supplier name "X" is already used.` | Supplier names are unique, case-insensitive | Use another name |
| `Family name is required.` / `Supplier name is required.` / `Description is required.` | Required field empty | Fill it in |
| `Cannot assign items to inactive family 'X'.` | You tried to put an item in a deactivated family | Reactivate the family, or pick an active one |
| `A reason is required to deactivate an item.` | Item deactivation always needs a reason | Choose *Temporarily unavailable / No longer commercialized / Other* |
| `A reason is required to activate an item.` | Reactivation needs a reason | Give one (e.g. *Genesis* on first activation) |
| `Enter a valid email address.` | Supplier email is malformed | Fix the email (or clear it) |
| `…selling price must be zero or greater.` | Prices can't be negative | Enter 0 (means "not priced") or a positive number |
| `…reorder level must be zero or greater.` | Reorder level can't be negative | Enter 0 or a positive number |
| `--retail-price must be greater than 0 when using --activate.` | `add_item` CLI was run with `--activate` but retail price is missing or zero | Pass `--retail-price` with a value greater than 0 |

**Family names are immutable** — the console has no "rename". If a name is wrong, deactivate it and create a new family (items keep the old family; you can't add new items to an inactive family).

**New items:** confirm **Genesis** on save — create and activation are atomic (no inactive orphan if you cancel). **Internal code** is required and locked after save.

**Manager catalog (`/manage/catalog/`)** — read-only stock + prices for warehouse staff. See [Manager catalog](07-manager-catalog.md).

| Message (exact) | Why it appears | What to do |
|-----------------|----------------|------------|
| `No items to show.` | No active items in active families | Create or reactivate items in the item console |
| `No items match these filters.` | Search, family, or “below reorder only” hid every row | Clear filters (*All families*, untick the checkbox) |
| `Could not load the catalog.` | Catalog API failed | Refresh; if it persists, ask an administrator |
| `The request could not be completed.` | Request failed without a specific message | Refresh; try again |
| `Catalogue view permission required` | Not a warehouse user (typical for branch-only logins) | Use `/branch/catalog/`, or ask head office for a warehouse group |

**Below reorder** is `reorder_level > 0` **and** stock ≤ reorder. Reorder **0** never flags. Buying price = primary supplier’s cost, else cheapest among **active** suppliers (else —).

### 2.2 Purchase orders (`/manage/purchase-orders/`)

| Message | Why | What to do |
|---------|-----|------------|
| `This supplier does not have a price for item X (id=N).` | That supplier has no `SupplierItemPrice` for the item — **no cross-supplier fallback** | Add a supplier price for that supplier+item, or choose a different item |
| `Cannot use inactive supplier 'X'.` / `Cannot use inactive item 'X'.` | The supplier or item was deactivated | Reactivate, or pick another |
| `This purchase order already has a line for 'X'.` | One line per item per PO (no merging) | Edit the existing line's quantity instead |
| `Purchase order lines can only be changed while the order is a draft.` | You tried to add/edit/remove a line after submit | Only drafts are editable |
| `Cannot submit a purchase order without lines.` | Submitting an empty PO | Add at least one line |
| `quantity must be greater than zero.` / `quantity is too large.` | Quantity ≤ 0, or ≥ 1,000,000,000 | Use a quantity in `(0, 1e9)` |
| `unit_cost must be zero or greater.` | Negative unit cost | Enter 0 or positive |
| `…must be between 0 and 100.` | A discount is negative or > 100% | Use 0–100 |
| `Commercial, financial and rappel discounts cannot exceed 100% combined.` | The three % add up past 100 | Lower them |
| `Cannot move a purchase order from 'X' to 'Y'.` | Illegal transition | See §4 |
| `You do not have permission to approve this purchase order.` | Operator, or grade too low | Operators never approve; managers need grade 2+ |
| `An approver is required.` | Approval without a user | Internal/system error — report it |
| `Self-approval is limited to … EUR gross (this PO is …).` | You're approving your **own** PO over your **self** cap | Ask another approver |
| `Approval is limited to … EUR gross (this PO is …).` | Approving someone else's PO over your cap | Ask a higher-grade approver |
| `No approval limit is configured for this grade.` | Missing `ApprovalLimit` row | Ask a warehouse admin to set it |
| `Only warehouse admins can change approval limits.` | Editing caps as non-admin | Warehouse admin only |
| `A reason is required to reject a purchase order.` | Reject needs a reason | Type one |
| `A reason is required to close a purchase order with remaining quantity.` | Manual close (short shipment) needs a reason | Type one |
| `A reason is required to cancel a purchase order.` | Cancel needs a reason | Type one |
| `A purchase order with receipts cannot be cancelled. Close it instead to accept a short shipment.` | You can't cancel an approved PO that already received goods | Use **close** (short shipment) instead |
| `Purchase order totals exceed the maximum supported value.` | Totals ≥ 1,000,000,000,000 | Lower quantities/prices |

### 2.3 Inventory — goods receipt, goods issue, branch stock

**Goods receipt (`/manage/goods-receipts/`)**

| Message | Why | What to do |
|---------|-----|------------|
| `Cannot receive goods against a purchase order with status 'X'.` | PO isn't **approved** or **received** | Approve it first |
| `Purchase order line not found on this purchase order.` | Line id doesn't belong to that PO | Re-select |
| `Each receipt line must be a valid object with line_id and quantity_received.` | Malformed line | Fix the form |
| `A purchase order line was provided more than once in this receipt.` | Duplicate line in one receipt | One row per PO line |
| `Received quantity X exceeds remaining Y for PO line N.` | Over-receipt | You can't receive more than ordered |
| `No lines to receive.` | Empty receipt | Add a line |
| `Stock cannot be adjusted below zero.` | Would make on-hand negative | Check your quantities |
| `A reason is required to adjust stock.` | `adjust_stock` needs a reason | Type one |

**Goods issue (warehouse, `/manage/internal-requests/`)**

| Message | Why | What to do |
|---------|-----|------------|
| `Cannot issue goods against a request with status 'X'.` | Request isn't **approved** or **fulfilling** | Only those are issuable |
| `Request line not found on this request.` | Wrong line id | Re-select |
| `Issued quantity X exceeds remaining Y for request line N.` | Over-issue vs the request | Lower it |
| `Insufficient stock for 'X': N requested, M on hand.` | Over-issue vs on-hand | The warehouse must procure first |
| `No lines to issue.` | Empty issue | Add a line |
| `A reason is required to short-close a request.` | Warehouse short-close needs a reason | Type one |

**Branch receipt & branch stock (`/branch/receipts/`)**

| Message | Why | What to do |
|---------|-----|------------|
| `Cannot receive against a request with status 'X'.` | Request isn't **shipped** or **received** | Wait for dispatch |
| `Goods issue line not found on this dispatch.` | Wrong line id | Re-select |
| `A goods issue line was provided more than once in this receipt.` | Duplicate line | One row per issue line |
| `Received quantity X exceeds shipped remaining Y.` | Over-receipt vs the dispatch | Lower it |
| `Only branch admins can adjust branch stock.` | Non-admin tried `adjust_branch_stock` | Branch admin only |
| `Branch stock cannot be adjusted below zero.` | Negative branch balance | Check your quantities |
| `A reason is required to adjust branch stock.` | Branch adjustment needs a reason | Type one |
| `A reason is required to short-close a request.` | Branch short-close needs a reason | Type one |

### 2.4 Requisição interna (`/branch/requests/`) & branches

| Message | Why | What to do |
|---------|-----|------------|
| `Item 'X' has no wholesale price.` | Wholesale is 0 — the requisição is priced from wholesale | Set a wholesale price (warehouse), or pick another item |
| `This request already has a line for 'X'.` | One line per item (no merging) | Edit the existing line |
| `Cannot use inactive item 'X'.` / `Cannot use inactive branch 'X'.` | Item or branch deactivated | Reactivate, or pick another |
| `Internal request lines can only be changed while the request is a draft.` | Editing after submit | Only drafts are editable |
| `Cannot submit a request without lines.` | Empty request | Add a line |
| `Cannot move an internal request from 'X' to 'Y'.` | Illegal transition | See §4 |
| `You do not have permission to approve or cancel this request.` | Operator (or cancelling approved as operator) | Manager/admin only |
| `Self-approval is limited to … EUR gross (this request is …).` | Manager approving own request over **self** cap | Ask another manager |
| `Approval is limited to … EUR gross (this request is …).` | Manager over **others** cap | Ask a higher approver |
| `No branch approval limit is configured for managers.` | Missing `BranchApprovalLimit` | Warehouse admin sets it |
| `A reason is required to reject a request.` | Reject needs a reason | Type one |
| `A reason is required to cancel an approved request.` | Cancel-approved needs a reason | Type one |
| `A request with goods issues cannot be cancelled.` | Goods already shipped | Short-close instead (see §4) |

### 2.5 Account, permissions & isolation

| What you see | When | Meaning |
|--------------|------|---------|
| `Authentication required` (401, JSON API) | Not signed in | Sign in |
| `Account is inactive` (403) | Your account was deactivated — you're signed out automatically | Contact your administrator |
| `Branch membership required` (403) | A warehouse-only user opened a `/branch/…` page | You need a branch role |
| `No active branch selected` (403) | Branch user with no branch chosen | Use the picker |
| `Internal request view permission required` (403) | A non-warehouse user opened `/manage/internal-requests/` | Warehouse role needed |
| `Missing permission: …` (403) | You lack a specific capability | See the role tables in 01–04 |
| **404 "not found"** | A request/dispatch from **another branch** | Branch data is **404**, not 403 — other branches are invisible, not merely forbidden |

> 💡 **403 vs 404:** *"You can't do that with your role"* → **403**. *"That row belongs to another branch"* → **404** (on purpose, so you can't even confirm it exists).

---

## 3. Numeric limits & precision

| Field | Storage | Valid range | Extra rule |
|-------|---------|-------------|------------|
| **Quantity** (PO line, request line, receipt, issue) | `Decimal(12,3)` | `> 0` and `< 1,000,000,000` | 3 decimal places |
| **Unit cost / unit price / selling prices / cost price** | `Decimal(12,2)` | `≥ 0` | 2 dp |
| **Approved totals & approval limits** | `Decimal(14,2)` | `< 1,000,000,000,000` | guarded against overflow |
| **Discounts** (commercial / financial / rappel) | `Decimal(5,2)` | each `0–100`; **combined ≤ 100** | percentages |
| **VAT rate** | `Decimal(5,4)` | fraction `0 … 1` | e.g. `0.16` = 16% |
| **Reorder level** | `Decimal(12,3)` | `≥ 0` | 0 = "no reorder trigger" |
| **Internal code** | `CharField` max **64** | required on console create; letters, digits, `.`, `-`, `_` only; **stored uppercase**; **immutable after save** (set-if-empty once for legacy) | unique, case-insensitive |
| **Retail price (Genesis)** | `Decimal(12,2)` | **> 0** required on console create / first activation | wholesale/special may stay 0 |
| **Reason / notes (reason fields)** | `CharField` / `TextField` | reason ≤ **255 chars** | over-long reason rejected |
| **Email** | `EmailField` | valid email | supplier & user |
| **Stock balances** (`Item.quantity`, `BranchItemStock.quantity`) | `Decimal(12,3)` | `≥ 0` | can't go negative |

**Rounding:** the whole app uses **half-away-from-zero** (`ROUND_HALF_UP` — not banker's rounding). Unit costs round to **4 dp** first, then line amounts (net / VAT / gross) round to **2 dp**.

---

## 4. State machines (every legal transition)

### 4.1 Purchase order

```text
draft ──submit──▶ submitted ──approve──▶ approved ──receive──▶ received ──close──▶ closed
  │                  │                     │                       │
  └── (draft edits)   └─reject─▶ rejected  └─cancel─▶ cancelled   └── (manual close = short shipment)
                                        └──reopen─▶ draft
```

- Only **draft** lines are editable.
- **Cancel** is only from **approved** and only with **zero receipts**; otherwise **close** (short shipment).
- **Reject** requires a reason; **reopen** moves `rejected → draft`.

### 4.2 Internal request (requisição)

```text
draft ──submit──▶ submitted ──approve──▶ approved ──issue──▶ fulfilling ──issue──▶ shipped
  │                  │                     │              │                         │
  │ cancel           └─reject (reason)     └─cancel       └─wh short-close          │
  ▼                                       │   (no dispatch)│                         ▼
cancelled                                cancelled         ▼               shipped ──receive──▶ received ──receive──▶ closed
                                                          closed                      │                     ▲
                                                                                      └── short-close ──────┘
```

**"Skip" transitions** (both happen automatically, in the same action):

- First issue that finishes the warehouse side → **`approved → shipped`** directly (never persists `fulfilling`).
- First receipt that finishes the branch side → **`shipped → closed`** directly (never persists `received`).

**Two short-closes:**

| Side | Who | Effect |
|------|-----|--------|
| Warehouse (`/manage/internal-requests/`) | Manager grade 2+ / admin, reason | **No dispatch yet** (`approved`, zero issued) → **closed**. **Partial issue** (`fulfilling`) → unshipped remainder written off → **shipped** |
| Branch (`/branch/receipts/`) | Manager / admin, reason | unreceived remainder written off → **closed** |

**No cancel after the first goods issue** — short-close only.

### 4.3 Inactive entities (lock 9 / D16)

- **Inactive branch:** blocks new requests/lines/submit/approve, but **in-flight** issue / branch receipt / short-close still work (stock in transit isn't stuck).
- **Inactive item/family:** blocks new lines / submit / approve. Existing lines keep their **snapshots** and can still be fulfilled.

---

## 5. Money, VAT & pricing edge cases

| Case | Behaviour |
|------|-----------|
| **Selling price = 0** | Means "not yet priced" — but a requisição line with **wholesale = 0 is rejected** |
| **Buying price (cost)** | From the **primary** supplier's price; if no primary, the **cheapest** supplier; if no prices at all → **no cost shown** |
| **One primary per item** | Marking a new supplier primary automatically **un-marks** the old one (DB-enforced) |
| **Supplier price** | Only for an **active** supplier **and** item; one cost per supplier×item |
| **Approved totals** | **Frozen at approval** — later price/VAT changes don't rewrite an approved PO/request (lines keep snapshots) |
| **VAT** | Stored as a fraction (`0.16`), applied per line at approval time |
| **Discounts** | Commercial + financial + rappel are all simple % now; combined > 100% is rejected |

---

## 6. Concurrency & audit guarantees

These are guarantees, not "best effort":

- **No lost updates / no overselling:** every write that touches stock or an order **locks the rows** (`select_for_update`), and stock items are locked in a **fixed (sorted) order** to avoid deadlocks. Two people receiving the last unit: one succeeds, the other gets an explicit "insufficient stock" error.
- **Append-only ledgers:** `StockMovement` and `BranchStockMovement` are never edited or deleted — only new rows. The cached `Item.quantity` / `BranchItemStock.quantity` are **computed** from the ledger; if they ever disagree, the ledger is the truth.
- **Frozen snapshots:** PO and request **lines** snapshot description, code, unit, VAT, price at creation/approval, so later master-data edits don't rewrite history.
- **Audit-by-design:** every create/update/lifecycle change writes a `*ChangeLog` row (`who`, `action`, `changes`, `reason`, `when`). There is no silent delete — deactivation/cancel instead.
- **Isolation:** one branch cannot read another branch's rows (404).

---

## 7. Known gaps (not built yet)

These are deliberate deferrals — ask before assuming they exist:

| Gap | Status |
|-----|--------|
| **Password reset** | No self-service reset; an administrator resets it |
| **Login rate-limiting** | **Pre-production blocker** — not implemented (documented) |
| **Email** | `notify_supplier_on_approval` is a **stub** (logs only) |
| **Offline / PWA** | Not built (Phase 7) |
| **Google OAuth / public signup** | Not implemented in dev |
| **Linked / auto purchase order** | Seam exists (nullable PO FK on request lines) but no automation |
| **Stock reservation** | Deferred — stock is checked at issue time, not reserved at approve |
| **Branch-tiered prices** | Only the 3 global selling prices (retail/wholesale/special) |
| **Categories / vector or LLM search / bulk import** | Not built |

---

## 8. Account & session edge cases

- **Login is by email** — there is no username field.
- **Deactivated mid-session:** the next request returns **"Account is inactive"** (403) and signs you out — even with a still-valid session cookie.
- **Timezone:** every user has a timezone (default `Europe/Lisbon`); invalid timezones are rejected at save. Server-rendered dates are shown in the viewer's timezone; stored in UTC.
- **`/admin/`** is **superuser-only**. Warehouse and branch staff never log into Django admin.
- **Dual warehouse + branch user:** after login they land on the **warehouse dashboard** (`/`); branch pages are still reachable by URL/picker.

---

## 9. Decision trees (quick reference)

**"I can't cancel."**
- PO: has receipts? → **close** (short shipment), not cancel.
- Request: already issued goods? → **short-close** (warehouse or branch), not cancel.
- Request, no issue yet, but I'm an operator → manager/admin only.

**"I can't approve."**
- Operator → never.
- Manager grade 1 → need grade 2+ (warehouse PO) / any manager (branch, within caps).
- Over your cap → ask a higher-grade approver.
- "No approval limit configured" → warehouse admin must set it.

**"I can't add a line."**
- Item inactive / family inactive / supplier inactive → reactivate.
- Wholesale = 0 (requisição) / no supplier price (PO) → fix pricing.
- Duplicate item on the document → edit the existing line.

**"My internal code was rejected."**
- Spaces or symbols (e.g. `@`, `#`) → use only letters, digits, `.`, `-`, `_`.
- Code already used (case-insensitive — `cem-50` collides with `CEM-50`) → pick another.
- Lowercase is fine — it is **saved as uppercase**.

**"I got 'insufficient stock'."**
- Issue: on-hand is less than requested → procure (PO → goods receipt) first.
- Receipt (branch): you typed more than the dispatch shipped.

---

## 10. Cross-references

- [Item Console](01-items.md) — catalogue, prices, families, suppliers, supplier prices.
- [Purchase Orders](02-purchase-orders.md) — PO workflow, discounts, approval.
- [Goods receipt & stock](03-goods-receipts.md) — receiving, stock ledger, adjustments.
- [Branches & Requisição interna](04-internal-requests.md) — the branch → warehouse → branch loop.
- [Manager catalog](07-manager-catalog.md) — warehouse read-only stock + prices (`/manage/catalog/`).
