# CentCompras — User Manual: Goods Receipt & Stock

**The Goods receipt console** · Version 1.0 · For warehouse staff (admin / manager / operator)

> **Also available:** the [Item Console manual](01-items.md), the [Purchase Orders manual](02-purchase-orders.md), the [Branches & Requisição interna manual](04-internal-requests.md), the [Edge cases & limits](05-edge-cases-and-limits.md) reference, and the [Admin & Superuser Reference](06-admin-reference.md).

---

## Where do I go?

> **Open your browser and go to:**
>
> **`https://<your-domain>/manage/goods-receipts/`**
>
> *(During development on your own machine: `http://127.0.0.1:8000/manage/goods-receipts/`)*

Sign in with your email + password. This manual assumes you already raise purchase orders; see the [Purchase Orders manual](02-purchase-orders.md) for draft → submit → approve.

You can also open this screen from an **approved** purchase order: click **Receive goods** (*Receber mercadoria*) in the PO drawer. That takes you here with the order already selected (`?po=<number>`).

---

## 1. Your role — what you can do

| Role | See receipts & movements | Record a receipt | Adjust stock |
|------|:---:|:---:|:---:|
| **Admin** (`warehouse_admins`) | ✅ | ✅ | ✅ |
| **Manager** (`warehouse_managers`) | ✅ | ✅ | ❌ |
| **Operator** (`warehouse_data_operators`) | ✅ (read-only) | ❌ | ❌ |

- **Operator** sees the same lists but has no **New receipt** or **Adjust stock** buttons.
- **Adjust stock** is the correction tool — **admin only**. Day-to-day receiving is a goods receipt, not an adjustment.
- The Django **`/admin/`** screen is for the **site superuser only** — it is *not* part of this manual.

A button missing from your screen is **not a bug**; it is not part of your role.

---

## 2. How stock works (read this once)

Stock is **never typed on the item**. You do not open an item and fill in a quantity.

```text
Approved purchase order
        ↓
  Goods receipt  (this console)
        ↓
  Stock movement  (+ quantity, signed)
        ↓
  Item quantity   (cached balance — updated automatically)
```

- Each receipt writes one **stock movement** per line received. The movement is **signed**: receipts are positive (`+10`), adjustments can be positive or negative (`+2` or `−2`).
- The number you see on the item later is a **cached balance** of those movements. If the two ever look wrong, trust the **Stock movements** table — that is the ledger.
- You cannot edit or delete a receipt after you confirm it. A mistake is corrected with a **new receipt** (if the PO still has remaining quantity) or an **admin stock adjustment**.

---

## 3. The console at a glance

> 📷 **[SCREENSHOT — goods receipt console, labelled]**

The screen is one page with a top bar, two action buttons, then two tables.

**A. Top bar**
- Title: **Goods receipt & stock** (*Receção de mercadorias e stock*)
- Signed in as *you@company*
- Language (English / Português), theme toggle, **Sign out**

**B. Toolbar**

| Button | Who sees it | What it does |
|--------|-------------|--------------|
| **New receipt** (*Nova receção*) | manager / admin | Record goods against an approved PO |
| **Adjust stock** (*Ajustar stock*) | admin only | Manual correction (count, damage, error) |

**C. Receipts table** — one row per goods receipt (a delivery you booked in).

| Column | Meaning |
|--------|---------|
| **GR #** (*N.º GR*) | Goods-receipt number |
| **PO #** (*N.º PO*) | The purchase order this delivery belongs to |
| **Supplier** | Who sent the goods |
| **Received by** | Who booked it in |
| **Received at** | Date/time (DD/MM/YYYY, 24h) |
| **Reference** | Supplier delivery note / *guia de entrega* (if you typed one) |
| **Total** | Sum of quantities on **this** receipt (not money) |

The receipts list is a log. There is no “open / edit” drawer on a receipt row.

**D. Stock movements table** — the ledger: every `+` and `−` against an item.

| Column | Meaning |
|--------|---------|
| **Item** | Internal code — description |
| **Type** | Receipt / Adjustment / Goods issue |
| **Quantity** | Signed amount (`+10` in, `−2` out) |
| **Reference** | For a receipt: `GR #12` and the delivery-note text if you entered one |
| **Reason** | Filled on adjustments |
| **By** / **When** | Who and when |

Use the **item filter** (*All items* / *Todos os artigos*) above the movements table to see one item’s history.

---

## 4. Recording a goods receipt

You can only receive against a purchase order that is **Approved** or already **Received** (a previous partial delivery). Draft, submitted, rejected, and closed orders do not appear in the list.

### 4.1 From this console

1. Click **New receipt** (*Nova receção*).
2. Choose the **Purchase order** (*Encomenda de compra*) — shown as `#12 — Supplier name`.
3. The lines of that order appear with **Ordered / Received / Remaining / To receive**.
4. **To receive** is pre-filled with the **remaining** quantity. Change it if this delivery is only part of the order. Set a line to **0** (or clear it) to skip it on this receipt.
5. (Optional) **Reference (delivery note)** (*Referência — guia de entrega*) — the supplier’s GR / *guia* number. Recommended: it appears on the receipt row and on the stock movement.
6. (Optional) **Notes**.
7. Click **Receive** (*Receber*).

You should see: *"Goods receipt recorded and stock updated."* (*Receção registada e stock atualizado.*)

The new row appears in **Receipts**, and matching **+** rows appear in **Stock movements**.

> 📷 **[SCREENSHOT — new receipt dialog with ordered / remaining / to receive]**

### 4.2 From the purchase-order console

1. Open the approved (or already received) PO.
2. Click **Receive goods**.
3. You land on this screen with that PO already chosen — continue from step 3 above.

### 4.3 Partial shipments

Several receipts against the same PO are normal.

| This delivery | What to type in **To receive** |
|---------------|--------------------------------|
| Full remaining quantity | Leave the pre-filled numbers |
| Only some of a line | Type the quantity that actually arrived (must be **greater than 0** and **not more than remaining**) |
| A line not on this truck | Leave **0** — that line is omitted from this receipt |

- You must receive **at least one** line with a quantity greater than zero.
- The app **rejects** a quantity that would go over the remaining amount. You cannot receive more than was ordered.
- Lines that are already fully received are hidden (you will see *"All lines on this purchase order are fully received."*).

### 4.4 What happens to the purchase order

| After this receipt | PO status |
|--------------------|-----------|
| First (or further) **partial** delivery | **Received** |
| Every line’s remaining quantity is now **0** | **Closed** (automatic) |

You do not close the PO by hand from this screen. Closing is the result of having received everything.

If the list of purchase orders is empty: *"No approved or partially-received purchase orders."* Approve a PO first, or the open ones are already closed.

---

## 5. Reading the stock movements ledger

This table is the audit trail for quantity.

| Type | When it appears | Quantity |
|------|-----------------|----------|
| **Receipt** (*Receção*) | You booked in a goods receipt | Positive (`+`) |
| **Adjustment** (*Ajuste*) | An admin used **Adjust stock** | Positive or negative |
| **Goods issue** (*Saída de mercadoria*) | A branch request was shipped (see the [branches manual](04-internal-requests.md)) | Negative (`−`) |

Filter by item when you are investigating one product. A receipt movement’s **Reference** column points back to the GR (`GR #4 — DN-001`).

---

## 6. Adjust stock (admin only)

Use this for **corrections**, not for supplier deliveries. Typical reasons: stock count, damaged goods, a receipt booked against the wrong quantity with no remaining PO quantity to fix it.

1. Click **Adjust stock** (*Ajustar stock*).
2. Choose the **Item**.
3. Enter **Quantity**:
   - **Positive** (e.g. `5`) — adds stock
   - **Negative** (e.g. `-5`) — removes stock
   - **0** is rejected
4. (Recommended) **Reason** — stored on the movement.
5. Click **Adjust** (*Ajustar*).

You should see: *"Stock adjusted."* (*Stock ajustado.*) A new row of type **Adjustment** appears in the ledger.

Managers and operators do not see this button. If a count is wrong, ask an admin.

---

## 7. What you cannot do here

- Receive against a PO that is not **Approved** or **Received**.
- Receive more than the remaining ordered quantity.
- Type stock on the item form in the item console — that field is not editable there.
- Edit or delete a goods receipt after it is saved.
- Issue stock to a branch from here — that is done in the [Branches & Requisição interna manual](04-internal-requests.md).
- Change selling prices or supplier costs — that stays in the [item console](01-items.md).

---

## 8. Dates, timezone, language & theme

Same as the other consoles:

- **Dates:** DD/MM/YYYY, 24-hour time (e.g. `20/08/2026 14:05`).
- **Timezone:** your local time (new users default to **Europe/Lisbon**).
- **Language:** English / Português (top-right; remembered).
- **Theme:** light / dark (top-right; remembered).

---

## 9. FAQ

**Q1. I don’t see my purchase order in the list — why?**
It must be **Approved** (or already **Received** from an earlier partial). Draft and submitted orders cannot be received. Closed and rejected orders cannot be received either.

**Q2. Can I receive a delivery in several lorries?**
Yes. Record one goods receipt per delivery. Remaining quantity shrinks each time. When remaining is 0 on every line, the PO **closes**.

**Q3. I typed too much on a receipt — can I edit it?**
No. Receipts are permanent. If the PO still has remaining quantity, do not “fix” it by receiving less next time unless that matches reality. If the item’s on-hand quantity is wrong, an **admin** uses **Adjust stock** with a reason.

**Q4. Why is the Total column not money?**
It is the **sum of quantities** on that receipt (pieces, kg, …), not the PO’s gross value. Money lives on the purchase order.

**Q5. Where do I see the item’s current stock?**
The cached balance is on the **manager catalog** at `/manage/catalog/` (stock + reorder level + buying/selling prices). You can also add the **+** and **−** rows for that item in **Stock movements**, or ask an admin to confirm in Django admin (superuser). Do not type a number onto the item.

**Q6. I can’t see “Adjust stock” — why?**
Only **admins** can adjust. Managers record receipts; operators are read-only. See §1.

**Q7. I can’t see “New receipt” — why?**
Your role is **operator**, or you don’t have add-receipt permission. You can still read the tables.

**Q8. What should I put in Reference?**
The supplier’s delivery note / *guia de entrega* number. It is optional but it is how you match a warehouse booking to a paper (or PDF) from the supplier.

**Q9. Does receiving change the purchase-order totals (net / VAT / gross)?**
No. Those figures were **frozen at approval**. Receiving only writes stock and moves the PO status to Received / Closed.

**Q10. Dates look like 05/08/2026 — is that 5 August or 8 May?**
**5 August 2026.** The app uses day/month/year everywhere.
