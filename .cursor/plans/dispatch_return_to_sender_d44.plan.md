---
name: Dispatch return to sender (D44)
overview: "Q1–Q8 locked 21 Sep. Fourth branch-receipt action: return an unbooked dispatch to the warehouse. New warehouse console to restock or write off. Alerts to warehouse + returning branch only. Distinct from D43. Awaiting explicit approval before code."
todos:
  - id: lock-questions
    content: "Q1–Q8 locked 21 Sep 2026 (Q6 = unbooked dispatch only)"
    status: completed
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

**Status:** product questions **locked** 21 Sep 2026. **Do not implement** until the user replies **approved**.

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
   │                      →  detailed qty alerts (warehouse + returning branch)
   └─ Write off damaged  →  stock stays down (already issued); audit row
                          →  detailed qty alerts (warehouse + returning branch)
```

Branch stock **does not go up** for returned qty (they never received it). This is not Consume and not Adjust.

---

## 3. Locked decisions (21 Sep 2026)

| ID | Topic | Choice |
|----|--------|--------|
| **P1** | **Where the button lives** | Fourth action on `/branch/receipts/`. Label EN **Return to sender** / PT **Devolver ao armazém**. |
| **P2** | **What is returned** | **All remaining** on the selected dispatch (every open line on that *guia*). Not the whole request. Later warehouse issues keep their own GI numbers (D42). |
| **P3** | **Exclusive with receive** | One click does not mix “keep some, return some”. Full remaining = Receive. Count dispute = Report discrepancies. Physical reject = Return. |
| **P4** | **Unbooked dispatch only** | Return only if this GI has **no** `BranchReceipt` (nothing booked, nothing discrepancy-written-off). After any receipt on this *guia*, hide Return. Shorts → discrepancy; owned stock going back → D43. |
| **P5** | **Who on the branch** | **Manager / admin**. Button **hidden** for operators. Operators keep Receive + Report discrepancies. |
| **P6** | **Confirm** | Native `confirm()` then a required **reason** `prompt()`. Online-only. |
| **P7** | **Issue document** | **Do not reverse** `GoodsIssue` / `GoodsIssueLine`. Restocked units join the **FIFO pool**. |
| **P8** | **Request header** | While `fulfilling`, **no status change**. After warehouse is done: if nothing remains to receive on any GI (received + discrepancy write-off + returned), **closed**. |
| **P9** | **No auto-reorder** | Warehouse processing has **Write off**, not Reorder. |
| **P10** | **Warehouse page** | **New** `/manage/returned-dispatches/` + dashboard card. Not mixed with D43 inbound or PO receipts. New sibling-nav item (e.g. **Returns**). |
| **P11** | **Warehouse who** | Inventory viewers can **see**; `inventory.add_goodsreceipt` **processes**. Warehouse cannot refuse. |
| **P12** | **Line mix at warehouse** | Per line, restock + write-off must cover remaining returned. Write-off requires a **reason**. |
| **P13** | **Restock ledger** | New `StockMovement.Type` e.g. `dispatch_return` (positive) + D32 FIFO. |
| **P14** | **Write-off ledger** | **No** second `StockMovement`. Line qty + append-only changelog. |
| **P15** | **Cancel in transit** | **No.** |
| **P16** | **Alerts destination** | Same `/manage/alerts/` and `/branch/alerts/`. |
| **P17** | **Alert audiences** | Warehouse **admin / manager g2+**; **returning** branch **manager / admin** only. No other branches. Operators 403. No email. |
| **P18** | **Alert payloads** | See §6. |
| **P19** | **Document number** | `DispatchReturn` shown as **DR #**. |
| **P20** | **i18n / manuals** | EN + PT same change. Manuals `04`, `05`, `03`, `06`. PROJECT-PLAN **D44**. |

---

## 4. Review answers (21 Sep)

| Q | Answer |
|---|--------|
| Q1 | Return **all** remaining on the selected dispatch. |
| Q2 | Restocked units join the **FIFO pool** (do not reverse the original issue). |
| Q3 | Alerts: **returning branch + warehouse** only. |
| Q4 | Write-off alerts: **warehouse + returning branch** only. |
| Q5 | **Hide** Return from operators. |
| Q6 | **Unbooked dispatch only** — no prior `BranchReceipt` on this GI. |
| Q7 | **No** in-transit cancel. |
| Q8 | **Return to sender** / **Devolver ao armazém**. |

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

- `return_dispatch(goods_issue, user, reason)` — manager/admin; remaining > 0; **no prior `BranchReceipt` on this GI**; creates DR + lines for every remaining line; opaque alerts.
- `process_dispatch_return(dr, lines, user)` — each entry `{line_id, quantity_restocked, quantity_written_off}`; write-off reason required if any write-off > 0; restock writes `StockMovement` + FIFO; write-off only line + changelog; emit detailed alerts per outcome present in that POST.
- Guards: cannot return a dispatch that already has a branch receipt; cannot receive/discrepancy a dispatch that has an open or processed DR; cannot process twice beyond remaining.

### 5.3 Branch UI (`/branch/receipts/`)

- Button **Return to sender** **hidden** for operators. Shown for manager/admin when a dispatch is selected, remaining > 0, and **this GI has no branch receipt**.
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

Q2 is locked: do **not** reverse the issue. Restocked units are free warehouse stock and FIFO may reserve them for a different waiting requisição.

---

## 6. Alerts

| Event | Details on the card | Who |
|-------|---------------------|-----|
| Branch confirms return | **No item/qty.** When, branch, request #, dispatch #, DR #. Reason **omitted** on the card (staff open the warehouse/branch work page if they need it) — or show reason without lines; confirm in Q-extra if you want reason visible. | Warehouse alerts + **returning** branch alerts |
| Warehouse restocks (qty > 0) | **Qty details:** code, qty restocked, DR #, dispatch #. | Warehouse + **returning** branch |
| Warehouse writes off (qty > 0) | **Qty details:** code, qty written off, reason, DR #. | Warehouse + **returning** branch |

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
- Tests: return while `fulfilling`; reject return if any `BranchReceipt` exists on the GI; cannot receive a returned dispatch; operator 403; restock FIFO; write-off does not bump `Item.quantity`; alerts omit qty on open and include qty on process; D43 path unchanged.
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

Product questions are locked. Reply **approved** to start implementation, or list exceptions.
