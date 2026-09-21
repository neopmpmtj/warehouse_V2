---
name: Dispatch return to sender (D44)
overview: "Plan only (no implementation until approved). Fourth branch-receipt action: return a dispatch to the warehouse. New warehouse console to restock or write off returned lines. Staged alerts. Distinct from D43 surplus send and from discrepancy reorder."
todos:
  - id: lock-questions
    content: "Resolve open product questions Q1–Q8 in this plan before writing code"
    status: pending
  - id: models-services
    content: "DispatchReturn document + lines + changelog; receive_return / restock / write_off in inventory.services"
    status: pending
  - id: branch-ui
    content: "Return to sender button + confirm/reason on /branch/receipts/; settle remaining on the selected guia"
    status: pending
  - id: warehouse-ui
    content: "New /manage/returned-dispatches/ console (not mixed with incoming-from-branches or goods receipts)"
    status: pending
  - id: alerts
    content: "Extend existing Alerts pages with typed cards: return opened (no qty), restocked (qty), written-off (qty)"
    status: pending
  - id: tests-docs
    content: "Django tests + EN/PT manuals 03/04/05/06 + PROJECT-PLAN D44 + i18n"
    status: pending
isProject: false
---

# D44 — Return to sender (dispatch return)

**Status:** discussion plan. **Do not implement** until this document is approved (with answers to the open questions).

**Origin:** branch receipts today have three outcomes for an open dispatch: full **Receive**, **Report discrepancies** (optional Reorder), and **Short close**. This slice adds a fourth: the branch **rejects the arrival and sends the goods back**. The warehouse then either **puts them on the shelf** or **writes them off** (damaged / not fit for stock).

**Does not replace:** D43 surplus send (`/branch/send-to-warehouse/` → `/manage/incoming-from-branches/`). D43 is on-hand the branch already owns. This slice is a *guia* that never (or no longer) belongs on the branch floor.

---

## 1. What exists today (so we do not collide)

| Path | When | Stock effect |
|------|------|----------------|
| **Receive** | Remaining of this dispatch arrived as shipped | Branch stock **up**. Request status unchanged while `fulfilling` (D42). |
| **Report discrepancies** | Count short of Remaining | Shortfall **written off on the guia** (cannot receive later). Warehouse **issue document unchanged**. Optional **Reorder** = new already-approved requisição. Alerts with **item/qty** to warehouse admin/manager g2+ and branch manager/admin. |
| **Short close** | Warehouse already done (`shipped` / `received`); pallet never booked | Writes off unreceived remainder of the **whole request**. Manager/admin only. Disabled while `fulfilling`. |
| **D43 Send** | Surplus **on-hand** at the branch | Two confirmations. Not a return of a dispatch. Warehouse cannot refuse. FIFO restock. |

The screenshot of `/branch/receipts/` (Norte, Admin, dispatch **#10** / request **#37** `fulfilling`) is the surface that gets the fourth button.

---

## 2. Goal

```text
Warehouse issues GI #10  →  warehouse stock already DOWN
        ↓
Branch sees the pallet, decides it must not enter branch stock
        ↓
Return to sender  →  in transit back  →  opaque alerts (no qty)
        ↓
Warehouse console (NEW page)
   ├─ Restock fit units  →  warehouse stock UP + D32 FIFO
   │                      →  detailed qty alerts (warehouse + related branches)
   └─ Write off damaged  →  stock stays down (already issued); audit row
                          →  detailed qty alerts
```

Branch stock **does not go up** for returned qty (they never received it). This is not Consume and not Adjust.

---

## 3. Proposed locked decisions (approve or amend)

These are **recommendations**. Anything in §4 overrides them.

| ID | Topic | Proposed choice |
|----|--------|-----------------|
| **P1** | **Where the button lives** | Fourth action on `/branch/receipts/` next to Receive / Report discrepancies / Short close. Label EN **Return to sender** / PT **Devolver ao armazém**. |
| **P2** | **What is returned** | The **remaining unreceived qty of the selected dispatch** (all open lines on that *guia*). Not the whole request. Later warehouse issues keep their own GI numbers (D42). |
| **P3** | **Exclusive with receive** | One click does not mix “keep some, return some”. Full remaining = Receive. Count dispute = Report discrepancies. Physical reject = Return. (Use discrepancy if some units actually stayed at the branch.) |
| **P4** | **After a partial receive** | Remaining on that same *guia* may still be returned. |
| **P5** | **Who on the branch** | **Manager / admin** (same bar as short-close). Operators keep Receive + Report discrepancies. Rejecting a pallet is a reasoned override. |
| **P6** | **Confirm** | Native `confirm()` then a required **reason** `prompt()` (same pattern as short-close / discrepancy). Online-only (receipts are already out of Phase 6 offline). |
| **P7** | **Issue document** | **Do not reverse** `GoodsIssue` / `GoodsIssueLine`. Match discrepancy: the *guia* stays as shipped. Returned remaining is settled so it cannot be received later on this GI. |
| **P8** | **Request header** | While `fulfilling`, **no status change** (warehouse may still ship). After warehouse is done: if nothing remains to receive on any GI (received + discrepancy write-off + returned), **closed**. |
| **P9** | **No auto-reorder** | Warehouse processing has **Write off**, not Reorder. If the branch still needs the item, they raise a **new requisição** (or wait for a later issue on the same request if it is still `fulfilling`). |
| **P10** | **Warehouse page** | **New** `/manage/returned-dispatches/` + dashboard card. **Not** mixed into `/manage/incoming-from-branches/`, `/manage/goods-receipts/`, or `/manage/internal-requests/`. New sibling-nav item (e.g. **Returns**). |
| **P11** | **Warehouse who** | Same as inbound receive: viewers with inventory can **see**; `inventory.add_goodsreceipt` (manager/admin) **processes**. Warehouse **cannot refuse** the return; they must restock and/or write off until remaining is 0. |
| **P12** | **Line mix at warehouse** | Per line, restock qty + write-off qty must sum to remaining returned. Some bottles on a pallet can go back on the shelf and some can be scrapped. Write-off requires a **reason**. |
| **P13** | **Restock ledger** | New `StockMovement.Type` e.g. `dispatch_return` (positive). Then D32 `allocate_available_stock` (FIFO to waiting `approved`/`fulfilling` lines). Not `receipt` (that is PO) and not `branch_inbound` (that is D43). |
| **P14** | **Write-off ledger** | **No** second `StockMovement` (warehouse qty already fell at issue). Persist write-off on the return **line** + append-only **changelog** (who, when, item, qty, reason). Superuser `/admin/` inspect-only. |
| **P15** | **Cancel in transit** | **v1: no.** Once the branch confirms, the document is `in_transit` until the warehouse processes. |
| **P16** | **Alerts destination** | **Same** `/manage/alerts/` and `/branch/alerts/` (typed cards). Do not invent a third alerts app. Discrepancy cards stay as they are. |
| **P17** | **Alert audiences** | Same as discrepancy: warehouse **admin / manager g2+**; branch **manager / admin**. Operators 403. Per-user read-state. No email (Phase 9). |
| **P18** | **Alert payloads** | See §6. |
| **P19** | **Document number** | `DispatchReturn` shown as **DR #**. One DR per return action, FK to `GoodsIssue`. |
| **P20** | **i18n / manuals** | EN + PT in the same change. Manuals `04`, `05`, `03`, `06`. PROJECT-PLAN **D44**. |

---

## 4. Open questions (need your answer)

Please confirm or correct. Recommended defaults are in §3.

**Q1 — Pallet vs lines on the branch.**  
Is v1 “return **all remaining** on this dispatch” (pallet reject), or should the branch pick **lines / qty** to return (mirror Actual received)?

**Q2 — Original requisição after restock.**  
P7 says the GI is frozen, so restocked units join the **FIFO pool** and may be reserved for **another** branch that approved earlier. Alternative: reverse the issue (un-issue qty, restore reservation on request #37). Which do you want?

**Q3 — “Related branches” on restock alerts.**  
Options: (a) only the returning branch + warehouse; (b) every branch that currently has `approved`/`fulfilling` remaining for those items; (c) every branch. Recommendation: **(b)** for restock (qty details), **(a)** for write-off (scrap is not other branches’ business).

**Q4 — Write-off alerts.**  
Same audience as restock, or warehouse + returning branch only?

**Q5 — Operator.**  
P5 hides Return from operators. Should an operator be allowed to reject a pallet (like they can report a discrepancy)?

**Q6 — Partial receive then return.**  
P4 allows returning leftover qty on the same *guia*. Should Return be allowed **only when nothing has been received** on that dispatch?

**Q7 — In-transit cancel.**  
P15 says no. Do you want a manager/admin **Cancel return** (stock conceptually still “out”, document voided so they could Receive after all)?

**Q8 — Button copy.**  
**Return to sender** / **Devolver ao armazém**, or **Return items** / **Devolver**, or **Reject dispatch** / **Recusar expedição**?

---

## 5. Architecture (after approval)

```text
branch UI / warehouse UI / API views
        ↓
inventory/services.py   (thin views, PostgreSQL truth)
        ↓
DispatchReturn + DispatchReturnLine + DispatchReturnChangeLog
GoodsIssue unchanged (qty_issued stays)
```

### 5.1 Models (inventory)

**`DispatchReturn`**

- `goods_issue` FK, `branch` via the request (denormalise if it helps alerts)
- `status`: `in_transit` → `processed` (or keep `in_transit` until every line is fully restocked or written off)
- `returned_by`, `returned_at`, `return_reason`
- `processed_by`, `processed_at` (last action; changelog has the history)
- Optional: multiple warehouse actions until remaining is 0 (like partial D43 receive)

**`DispatchReturnLine`**

- FK `goods_issue_line`
- `quantity_returned` (frozen at branch confirm)
- `quantity_restocked` (default 0)
- `quantity_written_off` (default 0)
- Check: restocked + written_off ≤ returned; all ≥ 0

Remaining on the *guia* for branch receive becomes:

```text
issued − already_received − discrepancy_write_off − returned
```

**`DispatchReturnChangeLog`** (audit)

- `action`: `returned` | `restocked` | `written_off`
- `user`, `at`, `reason`, `changes` JSON (line_id, qty, item code)

**Alerts read-state:** either reuse a generic `AlertReadState` keyed by `(user, kind, object_id)` or add `DispatchReturnReadState` **plus event kind** so the same DR can produce three cards (opened / restocked / written-off) with independent unread flags. Recommendation: **generic event table** `InventoryAlert` (kind, subject GFK, payload JSON, created_at) + `InventoryAlertReadState`, and **migrate existing discrepancy cards** onto it so `/manage/alerts/` is one feed. If that is too invasive, keep discrepancy as today and **append** return events beside them with a `kind` field in the JSON list.

### 5.2 Services

- `return_dispatch(goods_issue, user, reason)` — manager/admin; remaining > 0; creates DR + lines for every line with remaining; opaque alerts.
- `process_dispatch_return(dr, lines, user)` — each entry `{line_id, quantity_restocked, quantity_written_off}`; write-off reason required if any write-off > 0; restock writes `StockMovement` + FIFO; write-off only line + changelog; emit detailed alerts per outcome present in that POST.
- Guards: cannot receive/discrepancy qty that is already on an open or processed DR; cannot return qty already received or discrepancy-written-off; cannot process twice beyond remaining.

### 5.3 Branch UI (`/branch/receipts/`)

- Button **Return to sender**, enabled when a dispatch is selected, remaining > 0, and role is manager/admin. Disabled for operators (hidden or disabled + hint).
- Confirm + reason. On success the dispatch leaves the open list if remaining is 0; history can show a Returns/DR row (or a column on Receipts — prefer a small **Returns** table or a type on history so BR and DR are not confused).
- Short close unchanged (whole request, warehouse done, never booked). Return is per *guia* and can happen while `fulfilling`.

### 5.4 Warehouse UI (`/manage/returned-dispatches/`)

Layout close to `/manage/incoming-from-branches/` and to discrepancy columns:

- Left: in-transit / processed list (DR #, branch, request #, dispatch #, status, when).
- Right: lines — code, description, returned, already restocked, already written off, remaining, **Restock qty**, **Write off** checkbox, **Write-off qty**.
- Primary **Restock**; write-off is the discrepancy-Reorder analogue (explicit, reasoned).
- History of processed DRs + link to stock movements (`dispatch_return`).

Dashboard: warehouse card **Returned dispatches**. Do **not** put this queue on the D43 inbound page.

### 5.5 FIFO / reservation

On restock only: same helper as PO receipt and D43 inbound (`allocate_available_stock`). Write-off does **not** free warehouse on-hand (it was already issued). Negative `adjust_stock` still cannot go below reserved (R11).

If Q2 chooses **reverse the issue** instead of P7, restock would instead restore `quantity_reserved` on the **original** lines and reduce `quantity_issued` (or add a negative GI adjustment). That is a larger change to D42 and is **not** the default.

---

## 6. Alerts

| Event | Details on the card | Who |
|-------|---------------------|-----|
| Branch confirms return | **No item/qty.** When, branch, request #, dispatch #, DR #. Reason **omitted** on the card (staff open the warehouse/branch work page if they need it) — or show reason without lines; confirm in Q-extra if you want reason visible. | Warehouse alerts + **returning** branch alerts |
| Warehouse restocks (qty > 0) | **Qty details:** code, qty restocked, DR #, dispatch #. | Warehouse + **related branches** (Q3) |
| Warehouse writes off (qty > 0) | **Qty details:** code, qty written off, reason, DR #. | Q4 |

Unread badge on the existing Alerts dashboard card counts **all** unread kinds. Opening a card marks **that event** seen for that user.

“Without specific details” on the first event means: **do not list SKUs or quantities**. Identifiers (branch, request, dispatch, DR) are enough to find the document.

---

## 7. Explicit non-goals (v1)

- Do not mix with D43 BWS or PO goods receipts.
- Do not email (Phase 9).
- Do not offline-queue returns.
- Do not let the warehouse refuse / bounce the pallet back to the branch.
- Do not auto-create a follow-up requisição (that is discrepancy Reorder).
- Do not restyle the rest of the receipts page.
- Do not start Phase 7/8.

---

## 8. Docs and tests (when coding starts)

- EN + PT: `04-internal-requests.md` §8 (new 8.x Return to sender + warehouse processing), `05-edge-cases-and-limits.md` error strings, `03-goods-receipts.md` movement type, `06-admin-reference.md` URLs/roles.
- `docs/PROJECT-PLAN.md` D44 row; handoff after ship.
- Tests: return while `fulfilling`; cannot receive returned qty; operator 403; restock FIFO; write-off does not bump `Item.quantity`; alerts omit qty on open and include qty on process; D43 path unchanged.
- `node --check` + `?v=` bumps + branch SW precache if receipts JS is extracted/cached.

---

## 9. Implementation slices (after approval)

1. Models + migration + services + tests (no UI).
2. Branch button + API.
3. Warehouse console + nav/card.
4. Alert types + unread counts.
5. Manuals + i18n + living docs.

---

## 10. How to approve

Reply with: **approved as written**, or **approved except** (list P-ids / Q-ids). Implementation starts only after that reply.
