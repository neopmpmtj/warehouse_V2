# CentCompras — User Manual: Branches & Requisição interna

**Branch ordering** · Version 1.0 · For branch staff (operator / manager / admin) **and** warehouse staff

> **Also available:** the [Item Console manual](01-items.md) · [Purchase Orders](02-purchase-orders.md) · [Goods receipt & stock](03-goods-receipts.md) · [Manager catalog](07-manager-catalog.md) · [Edge cases & limits](05-edge-cases-and-limits.md) · [Admin & Superuser Reference](06-admin-reference.md).
>
> This manual covers everything a **satellite branch** does, plus the **warehouse** side of the same loop. Read it end-to-end once — the loop only makes sense as a whole.

---

## The big picture

A branch orders from the central warehouse through a **Requisição interna** (internal request). The loop:

```text
Branch browses catalogue   (cost hidden, stock as a hint)
        ↓
Branch raises a requisição (draft)
        ↓
Branch manager approves    (freezes totals; gross shown before confirm)
        ↓
Warehouse ships            (goods issue — central stock goes DOWN)
        ↓
Branch confirms arrival    (branch receipt — branch stock goes UP)
```

Out of stock? The warehouse raises a **purchase order** to a supplier first — see the [Purchase Orders](02-purchase-orders.md) and [Goods receipt](03-goods-receipts.md) manuals. That part is unchanged.

---

## Where do I go?

| Who | Page | What for |
|-----|------|----------|
| Branch (any role) | `/branch/select/` | Choose your branch |
| Branch (any role) | `/branch/catalog/` | Read-only catalogue (cost hidden, stock hint) |
| Branch (any role) | `/branch/requests/` | Raise & edit a requisição |
| Branch (manager / admin) | `/branch/requests/` | Approve / reject |
| Branch (any role) | `/branch/receipts/` | Confirm arrival against a dispatch |
| Warehouse | `/manage/internal-requests/` | Queue of approved requests + goods issue |
| Warehouse admin | `/manage/branch-approval-limits/` | Branch manager approval caps |

*(During development on your own machine: `http://127.0.0.1:8015/…`.)*

> 📷 **[SCREENSHOT — branch home (catalogue) with top bar]**

---

## 1. Your role — what you can do

There are **three branch roles** (set for you by the head office) and the usual **warehouse roles**. A button missing from your screen is **not a bug** — it is not part of your role.

### 1.1 Branch roles

| Capability | Operator | Manager | Admin |
|-----------|:---:|:---:|:---:|
| Browse catalogue | ✅ | ✅ | ✅ |
| Raise & edit a draft, submit, cancel a draft | ✅ | ✅ | ✅ |
| Approve / reject | ❌ | ✅ (within caps) | ✅ (unlimited) |
| Cancel an **approved** request | ❌ | ✅ | ✅ |
| Confirm arrival (branch receipt) | ✅ | ✅ | ✅ |
| Branch short-close | ❌ | ✅ | ✅ |
| Adjust branch stock | ❌ | ❌ | ✅ |

- **Operator** can do the day-to-day (catalogue, request, receipt) but never approves and never short-closes.
- **Manager** adds approval/rejection/short-close, within **EUR gross caps** (self vs others — see §8).
- **Admin** is the branch power user: unlimited approval, plus **branch stock adjustments**.
- The Django **`/admin/`** screen is for the **site superuser only**. Branch staff never log into `/admin/`. Head office creates your login and your branch role there.

### 1.2 Warehouse roles (the other half of the loop)

| Capability | Who |
|-----------|-----|
| See the request queue + issue goods | Operator grade 2+, manager, admin |
| Warehouse short-close | Manager grade 2+ or admin |
| Edit branch approval caps | Warehouse admin (`/manage/branch-approval-limits/`) |

---

## 2. Choosing your branch (the picker)

You may belong to **one branch, several branches, or none**. After signing in:

| Your situation | What happens |
|----------------|--------------|
| **One branch** | You go straight to that branch (no picker). |
| **Several branches** | You land on `/branch/select/` — pick one. |
| **No branch** | The picker says *"You have no active branch access."* Ask your administrator. |

To switch later, click **Switch branch** on any branch page. **Sign out** is in the **Settings** gear (top-right); extra links such as **Catalog**, **Requests**, and **Switch branch** stay visible in the header. **Help** in that panel is a placeholder.

> 📷 **[SCREENSHOT — branch picker with two branches listed]**

---

## 3. The branch catalogue (read-only)

Open **`/branch/catalog/`**. This is the same product catalogue the warehouse manages, but with two deliberate differences:

1. **Cost is hidden.** You see the **selling prices** (Retail / Wholesale / Special), never the supplier cost.
2. **Stock is only a hint** — never an exact number.

Warehouse staff see exact stock **and** cost on the [manager catalog](07-manager-catalog.md) at `/manage/catalog/`.

### 3.1 The availability hint

| Hint | Meaning |
|------|---------|
| **In stock** | Something is **free to ship today** (available stock above the reorder level). |
| **Low** | Free-to-ship quantity is at or below the reorder level — request soon. |
| **None** | Nothing is free to ship **today** (the shelf is empty, or everything on the shelf is already held for earlier approved requisições). You may still raise a requisição — the warehouse will procure and you wait in line. |

You will **not** see the exact on-hand quantity — that is a warehouse figure. **None does not block a requisição.**

---

## 4. Raising a requisição

Open **`/branch/requests/`**.

### 4.1 Create a draft

1. Click **New request** (*Nova requisição*).
2. The request starts as a **draft**.

### 4.2 Add lines

1. In the line form, pick an **item** from the catalogue picker.
2. Enter the **quantity** (greater than zero).
3. Click **Add**.

A line is **rejected** if:

- the item has **no wholesale price**, or
- the item is **already** on this request (edit the existing line instead), or
- the item (or its family) is **inactive**.

You can **remove** a line while the request is still a draft.

### 4.3 Submit

When the request has at least one line and everything is active, click **Submit** (*Submeter*). The request becomes **submitted** and waits for a manager.

- You can no longer edit lines after submitting.
- A **draft** can be **cancelled** by any branch role (no reason needed).

---

## 5. Approve / reject (manager or admin)

Open a **submitted** request.

### 5.1 Approve

1. Click **Approve** (*Aprovar*).
2. The confirmation shows the **gross** (wholesale × quantity + VAT) — review it.
3. Confirm.

Approving **freezes the totals** — the prices and VAT are snapshotted at this moment, so later price changes don't rewrite history.

Approving also **holds whatever warehouse stock is currently free** for this request (see §7). A later branch cannot take those units. If the hub has less than you asked for, the request is still approved: the free portion is held, and the rest waits for incoming stock (first approved wins).

| Approver | Limit |
|----------|-------|
| **Admin** | Unlimited |
| **Manager** | EUR gross caps: one for **your own** requests, one for **other people's** (set by the warehouse admin, §8) |

### 5.2 Reject

Click **Reject** (*Rejeitar*) and give a **reason**. The request ends as **rejected** — raise a new one if you still need the goods.

> 📷 **[SCREENSHOT — approve confirmation showing gross]**

---

## 6. Cancelling a request

| From | Who | Reason required? |
|------|-----|:---:|
| **Draft** | Any branch role | No |
| **Approved** | Manager / admin | Yes |

Cancelling an **approved** request (no dispatch yet) **releases the hold** immediately; those units are offered to the next waiting requisição (oldest `approved_at` first).

Once the warehouse has **shipped** (issued goods), a request can no longer be cancelled — only **short-closed** (§7 / §8). That rule stops stock from being dispatched and then "un-dispatched".

---

## 7. Warehouse — ship (goods issue)

Open **`/manage/internal-requests/`**. This queue shows **approved** and **fulfilling** requests only — never drafts, submitted, rejected, or cancelled. The header keeps **Branch caps**. **Sign out** is in the **Settings** gear (top-right).

### 7.1 Issue goods

1. Select a request.
2. For each line you are shipping now, type the **issue quantity**.
3. (Optional) **Reference** (your *guia* / dispatch number) and **Notes**.
4. Click **Issue** (*Emitir*).

Rules:

- You cannot issue **more than is reserved for this request** (the quantity held at approve, plus any later incoming stock allocated to it).
- You cannot issue **more than the request's remaining** quantity.
- **Partial issue** is fine — the request becomes **fulfilling** and the rest ships later.
- A **complete** issue marks the request **shipped**.

The queue shows **reserved**, **backorder** (still waiting for stock), **on hand**, and **available** (on hand minus all holds) per line. Issue quantity defaults to the reserved amount.

Issuing **decrements central stock** and the hold together.

If another branch is first in line for free stock, you cannot ship to a later request until that hold is issued, cancelled, or short-closed (reason required).

### 7.2 Warehouse short-close

If you can't (or won't) ship the rest, click **Short close** and give a **reason**. The unshipped remainder is written off and any hold on that remainder is **released** to the next waiting requisição (oldest `approved_at` first).

- If **nothing was dispatched yet** (request still **approved**), the request becomes **closed** — there is nothing for the branch to receive.
- If you already **partially issued** goods (request **fulfilling**), the request becomes **shipped** so the branch can receive what was sent and short-close any remainder.

Only a **manager grade 2+ or admin** can do this.

![Warehouse internal-requests queue](screenshots/07-internal-requests.png)

---

## 8. Branch — confirm arrival (receipt)

Open **`/branch/receipts/`**. It lists the **dispatches** (*guias*) for your branch — requests that are **shipped** or **received** (i.e. on their way or partly arrived).

### 8.1 Receive against a dispatch

1. Select a dispatch.
2. For each line, type the **received quantity** (what actually arrived — damage or shortage means you type less).
3. Click **Receive** (*Receber*).

Rules:

- You cannot receive **more than was shipped** on that line.
- **Partial** receipt → request stays **received** (more still expected).
- **Full** receipt → request becomes **closed**.

Receiving **increments branch stock** immediately.

### 8.2 Branch short-close

If the rest won't arrive, click **Short close** and give a **reason**. The unreceived remainder is written off and the request becomes **closed**. Only a **manager or admin** can do this.

> 📷 **[SCREENSHOT — branch receipt with received quantities]**

---

## 9. Branch stock adjustment (admin only)

Branch **admin** may correct branch stock directly — for counts, damage, or mistakes.

1. On `/branch/receipts/`, use the **Adjust stock** area.
2. Enter **Item**, **Quantity** (positive to add, negative to remove — `0` is rejected), and a **Reason**.
3. Click **Adjust stock**.

Managers and operators do not see this option. Branch stock is a ledger like warehouse stock — every receipt and adjustment is recorded and the balance is computed, never typed onto the item.

---

## 10. Branch approval caps (warehouse admin)

Open **`/manage/branch-approval-limits/`** (warehouse **admin** only). This sets how much a branch **manager** may approve, in **EUR gross**. The header keeps **Requests**. **Sign out** is in the **Settings** gear.

- **Others** — the cap when the manager approves someone else's request.
- **Self** — the (lower) cap when the manager approves their **own** request.

Branch **admins** have no cap (unlimited). Operators never approve. These caps are global across all branches in this phase.

> 📷 **[SCREENSHOT — branch approval limits editor]**

---

## 11. The request life (status cheat-sheet)

```text
draft ──submit──▶ submitted ──approve──▶ approved ──issue──▶ fulfilling ──issue──▶ shipped
   │                  │                     │                                     │
   │ cancel (no       │ reject (reason)      │ cancel (reason, no shipments yet)  │
   │  reason)         ▼                     ▼                                     ▼
   └──────────────▶ cancelled            rejected                    shipped ──receive──▶ received ──receive──▶ closed
                                                                                       │                     ▲
                                                                                       └── short-close ──────┘
```

| Status | Meaning |
|--------|---------|
| **draft** | Branch is building it |
| **submitted** | Waiting for a branch manager |
| **approved** | Visible to the warehouse; not yet shipped |
| **rejected** | Manager rejected it (terminal) |
| **fulfilling** | Partly shipped; warehouse remainder still open |
| **shipped** | Warehouse done (fully issued or short-closed) |
| **received** | Partly arrived; branch remainder still open |
| **closed** | Branch done (fully received or short-closed) |
| **cancelled** | Voided before any goods issue |

---

## 12. What you cannot do here

- See the supplier **cost** from a branch account (selling prices only).
- See the **exact** warehouse stock from a branch account (hint only).
- Approve as an **operator**, or approve over your **manager cap**.
- Request an **inactive** item, or a line with **no wholesale price**, or the **same item twice** on one request.
- Edit a request after **submit**.
- **Issue** more than is reserved for that request, or more than the request's remaining.
- **Receive** more than was shipped.
- **Cancel** a request after goods have been issued (short-close instead).
- Short-close as an **operator** (either side).
- Adjust branch stock unless you are the branch **admin**.

---

## 13. Dates, timezone, language & theme

Same as the other consoles:

- **Dates:** DD/MM/YYYY, 24-hour time (e.g. `20/08/2026 14:05`).
- **Timezone:** your local time (new users default to **Europe/Lisbon**).
- **Language:** English / Português (top-right; remembered).
- **Theme:** light / dark (top-right; remembered).

---

## 14. Related consoles

- [Item Console](01-items.md) — where the warehouse manages the catalogue (items, families, suppliers, prices).
- [Manager catalog](07-manager-catalog.md) — warehouse read-only stock + prices (`/manage/catalog/`; cost visible).
- [Purchase Orders](02-purchase-orders.md) — how the warehouse restocks from suppliers.
- [Goods receipt & stock](03-goods-receipts.md) — booking supplier deliveries into central stock.

---

## 15. FAQ

**Q1. Why can't I see the cost price in the branch catalogue?**
Deliberate. Branches see selling prices only; supplier cost is warehouse-confidential. Warehouse staff see cost on the [manager catalog](07-manager-catalog.md) at `/manage/catalog/`. If you need a price you can't see, ask the warehouse.

**Q2. The catalogue says "None" for an item — can I still request it?**
Yes. **None** means nothing is free to ship *today* (empty shelf, or stock already held for earlier approved requisições). Raise the requisição anyway — you join the wait. Incoming stock is offered to the oldest approved request first.

**Q3. Why was my line rejected?**
The three rules: the item must have a **wholesale price**, it must be **active**, and it must not already be on the request. Check which one applies.

**Q4. I approved a request and the prices changed later — did my request change?**
No. Approving **freezes** the totals (wholesale + VAT snapshot). Later price changes don't touch an approved request.

**Q5. The warehouse shipped less than I asked — what do I do?**
Confirm the **received quantity** that actually arrived at `/branch/receipts/`. If the rest won't come, a **manager/admin** short-closes it. The request then closes.

**Q6. I can't see "Approve" — why?**
You're an **operator** (operators never approve), or the request isn't **submitted**. Ask a manager, or submit first.

**Q7. I can't see "Short close" — why?**
Short-close is manager/admin only, on both the warehouse and branch side.

**Q8. Can I request the same item twice?**
No — one line per item per request. **Edit** the line's quantity instead of adding a second line.

**Q9. My branch login says "no active branch access" — what's wrong?**
Head office hasn't assigned you to a branch (or your branch is inactive). Contact your administrator — branch access is set up in Django `/admin/`, not by you.

**Q10. What does "gross" mean on the approve button?**
The request's total **including VAT** (wholesale × quantity, plus VAT). That's the figure your approval cap is measured against.

**Q11. Another branch asked for the same item after us — will they take our stock?**
No, once your requisição is **approved**. The warehouse holds the free quantity for you. A later branch can still approve (and wait), but they cannot be issued those held units.

**Q12. We cancelled an approved request — what happens to the hold?**
The hold is released immediately and offered to the next waiting requisição (oldest first).

**Q13. Why can't I cancel an approved request after the warehouse shipped?**
Stock is already in motion. After the first goods issue the only way to finish early is **short-close** (warehouse side) or **branch short-close** (branch side).

**Q14. How is branch stock different from warehouse stock?**
Two separate ledgers. Warehouse stock lives on the item; **branch stock** lives per `(branch, item)` and only moves when you receive a dispatch or an admin adjusts it.
