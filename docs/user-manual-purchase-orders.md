# CentCompras — User Manual: Purchase Orders

**The Purchase Orders console** · Version 1.0 · For warehouse staff (admin / manager / operator)

---

## Where do I go?

> **Open your browser and go to:**
>
> **`https://<your-domain>/manage/purchase-orders/`**
>
> *(During development on your own machine: `http://127.0.0.1:8000/manage/purchase-orders/`)*

Sign in with your email + password (the one your administrator gave you). This manual assumes you already know the item catalogue; see the [Item Console manual](user-manual.md) for items, families, suppliers, and supplier prices.

---

## 1. Your role — what you can do

| Role | See POs | Create / edit | Approve |
|------|:---:|:---:|:---:|
| **Admin** (`warehouse_admins`) | ✅ | ✅ | ✅ |
| **Manager** (`warehouse_managers`) | ✅ | ✅ (no approve) | ❌ |
| **Operator** (`warehouse_data_operators`) | ✅ (read-only) | ❌ | ❌ |

- **Operator** sees the list but has no "New purchase order" button and no edit/status buttons.
- **Approve** is the finance step — only admins can do it.

---

## 2. The console at a glance

> 📷 **[SCREENSHOT — purchase orders list]**

**Toolbar:** a **status filter** (All / Draft / Submitted / Approved / Received / Closed / Rejected) and a **New purchase order** button.

**Table columns:**

| Column | Meaning |
|--------|---------|
| **PO #** | Purchase order number |
| **Supplier** | Who we're buying from |
| **Status** | Where the order is in the workflow |
| **Total** | The **gross** amount (net + VAT) — the full cost to fund |
| **Created** | Date/time (DD/MM/YYYY) |
| **Actions** | **Open** |

Click a row (or **Open**) to see the full order in a drawer.

---

## 3. Creating a purchase order

1. Click **New purchase order** (*Nova encomenda*).
2. Pick the **Supplier**.
3. (Optional) add a **Supplier ref** and **Notes**.
4. Click **Create**.

The order starts as a **Draft**.

---

## 4. Adding lines

1. Open the order (click its row).
2. Click **Add line** (*Adicionar linha*).
3. Pick the **Item**, enter a **Quantity**, and (optionally) a **Unit cost**.
4. Leave **Unit cost blank** to auto-fill it from the supplier's price list.
5. (Optional) set the three discounts (see §5).
6. **Save**.

> ⚠️ **The supplier must have a price for the item.** If the supplier has no price for the item you picked, the line is **rejected** with a message — *"This supplier does not have a price for this item. Add it under Suppliers → Supplier prices first."* This is by design: a purchase order to a specific supplier should only contain items that supplier carries. To order such an item, first add its price in the item console (Suppliers → Supplier prices).

- **Edit / remove** a line is only possible while the order is a **Draft** (and needs edit permission).

---

## 5. Discounts (commercial / financial / rappel)

Each line can carry three percentage discounts:

| Discount | Meaning |
|----------|---------|
| **Commercial %** | Trade discount off the unit price |
| **Financial %** | Prompt-payment / financial discount |
| **Rappel %** | Volume rebate (kept simple for now) |

Rules:
- Each discount is **0–100%**.
- **Combined** they cannot exceed **100%** — the app rejects it if the total would make the price negative.
- They apply to the net unit cost **before VAT**.

---

## 6. Net / VAT / Gross totals

Each line and the whole order shows three figures:

| Figure | Meaning |
|--------|---------|
| **Net** | after discounts, before VAT |
| **VAT** | the tax amount |
| **Gross (Total)** | net + VAT — **the full amount to fund** |

The list's **Total** column shows the **gross**.

---

## 7. The approval workflow

| From | Action | To | Who |
|------|--------|----|-----|
| Draft | **Submit** | Submitted | manager/admin |
| Submitted | **Approve** | Approved | **admin only** |
| Submitted | **Reject** | Rejected | manager/admin |
| Approved | **Receive** | Received | manager/admin |
| Received | **Close** | Closed | manager/admin |

- **Submit** requires at least one line.
- Once submitted, lines are **locked** — you can no longer edit them.
- **Approve** freezes the totals (see §8).

> ⚠️ **Receive** currently only changes the status — it does **not** yet write stock (that's the next phase, goods receipt).

---

## 8. Approved totals snapshot

When an admin **approves** a purchase order, the **Net / VAT / Gross** figures are **frozen** and stored with the order. From then on the drawer shows those frozen figures, so the approved record is immutable — even if discount or VAT rules change later.

---

## 9. History

Every action is recorded — who did it and when: created, line added/updated/removed, and each status change. Open an order and scroll to **History**.

---

## 10. FAQ

**Q1. I picked an item but the line was rejected — why?**
The supplier on this order has no price for that item (see §4). Add the price in the item console first, or pick a different supplier.

**Q2. What does "Primary" mean on a supplier price?**
It marks the supplier as the *preferred* supplier for that item. On a purchase order, the cost comes from **this order's supplier's** price — never another supplier's.

**Q3. Why can't I edit a line?**
Lines are editable only while the order is a **Draft**. After **Submit** they're locked.

**Q4. I can't see the "Approve" button — why?**
Only **admins** can approve. Managers can create and submit; operators are read-only.

**Q5. What's the difference between Net and Gross?**
Net is before VAT; Gross is net + VAT — the amount you actually pay.

**Q6. Dates and timezone?**
Dates show as DD/MM/YYYY, in your local timezone (default Europe/Lisbon). Language is EN / pt-PT.
