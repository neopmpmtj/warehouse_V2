# CentCompras — User Manual: Requisição interna & branch receipts

**Branches → warehouse → branches** · Version 1.0 · For branch staff (operator / manager / admin) and warehouse staff

---

## What is this?

A **Requisição interna** is how a satellite branch asks the central warehouse for stock. The loop is:

1. **Branch** browses the catalogue (cost hidden; stock shown as a hint) and raises a priced requisição.
2. A **branch manager** (or admin) approves it.
3. The **warehouse** sees approved requests, ships them (goods issue), and central stock goes down.
4. The **branch** confirms arrival against the dispatch (guia), and its own stock goes up.

---

## Where do I go?

| Who | Page | Purpose |
|-----|------|---------|
| Branch (any role) | `/branch/catalog/` | Read-only catalogue (cost hidden, stock hint) |
| Branch (any role) | `/branch/requests/` | Raise + edit a requisição |
| Branch (manager / admin) | `/branch/requests/` | Approve / reject |
| Branch (any role) | `/branch/receipts/` | Confirm arrival against a dispatch |
| Warehouse | `/manage/internal-requests/` | Queue of approved requests + goods issue |
| Warehouse admin | `/manage/branch-approval-limits/` | Branch manager approval caps |

*(During development on your own machine: `http://127.0.0.1:8000/…`.)*

---

## 1. Branch — raise a requisição

1. Open **`/branch/requests/`** (pick your branch first if prompted).
2. Click **New request**. It starts as a **draft**.
3. **Add line**: choose an item from the catalogue picker and enter a quantity. A line is rejected if the item has **no wholesale price** or is already on the request.
4. **Submit** when ready (≥1 line, all items active).

- A draft can be **cancelled** by any branch role.
- You cannot edit lines after submitting.

## 2. Branch — approve / reject (manager or admin)

1. Open the **submitted** request.
2. **Approve** freezes the totals (wholesale × quantity + VAT). The approve button shows the **gross** before you confirm.
3. **Reject** requires a reason.

- **Operator** can raise and submit but **never approves**.
- **Manager** approves within **EUR gross caps** (self vs others — set by the warehouse admin at `/manage/branch-approval-limits/`). **Branch admin** approves any amount.

## 3. Warehouse — ship (goods issue)

1. Open **`/manage/internal-requests/`** — shows **approved** and **fulfilling** requests only (never drafts or submitted).
2. Select a request and enter **issue quantities** per line (cannot exceed on-hand or the request's remaining).
3. **Issue** decrements central stock; a partial issue marks the request **fulfilling**, a complete one **shipped**.
4. **Short close** (manager grade 2+ or admin) writes off the unshipped remainder and marks it **shipped** — reason required.

## 4. Branch — confirm arrival (receipt)

1. Open **`/branch/receipts/`** — lists dispatches for your branch (requests that are shipped or received).
2. Select a dispatch and enter **received quantities** per line (cannot exceed what was shipped).
3. **Receive** writes branch stock up. Full receipt → request **closed**; partial → **received**.
4. **Short close** (manager / admin) writes off the unreceived remainder → **closed** — reason required.
5. **Branch admin** may **adjust branch stock** directly (reason required).

---

## Quick reference

| Action | Who |
|--------|-----|
| Browse catalogue / draft / lines / submit / cancel draft | Any branch role |
| Approve / reject | Branch manager (caps) / admin (unlimited) |
| Warehouse goods issue | Warehouse operator 2+ / manager / admin |
| Warehouse short-close | Warehouse manager grade 2+ / admin |
| Branch receipt | Any branch role |
| Branch short-close | Branch manager / admin |
| Branch stock adjust | Branch admin only |
