# CentCompras — User Manual: Manager Catalog

**The Manager catalog** · Version 1.0 · For warehouse staff (admin / manager / operator)

> **Also available:** [Item Console](01-items.md) at `/manage/items/` · [Purchase orders](02-purchase-orders.md) · [Goods receipt & stock](03-goods-receipts.md) · [Branches & Requisição interna](04-internal-requests.md) · [Edge cases & limits](05-edge-cases-and-limits.md) · [Admin & Superuser Reference](06-admin-reference.md).

This is the warehouse **read-only** overview: stock, reorder level, selling prices, buying price, and suppliers on one page. You do **not** edit items here — that is the [Item Console](01-items.md).

---

## Where do I go?

> **Open your browser and go to:**
>
> **`https://<your-domain>/manage/catalog/`**
>
> *(During development on your own machine: `http://127.0.0.1:8000/manage/catalog/`)*

Sign in with your warehouse email + password. The dashboard also lists this page as *manager catalog (stock + prices)*.

Branch staff do **not** use this URL. They browse the [branch catalogue](04-internal-requests.md) at `/branch/catalog/` (cost hidden, stock as a hint only).

---

## 1. Your role — what you can do

| Role | Open the page | See cost (buying price) | Edit anything here |
|------|:---:|:---:|:---:|
| **Admin** (`warehouse_admins`) | ✅ | ✅ | ❌ |
| **Manager** (`warehouse_managers`) | ✅ | ✅ | ❌ |
| **Operator** (`warehouse_data_operators`) | ✅ | ✅ | ❌ |
| **Branch staff** | ❌ | — | — |

- The whole page is **view-only** for every warehouse role — there is no Save, no New item, no Adjust stock.
- **Cost is warehouse-confidential.** That is why this page exists separately from `/branch/catalog/`.
- A button or column missing is **not a bug**; branch users who open `/manage/catalog/` are refused (*Catalogue view permission required*).
- The Django **`/admin/`** screen is for the **site superuser only** — it is *not* part of this manual.

To change an item, a price, or stock, use the consoles in §7.

---

## 2. What this page is (and is not)

```text
Item console (/manage/items/)     →  create / edit catalogue
Goods receipt (/manage/goods-receipts/)  →  stock goes UP
Goods issue (/manage/internal-requests/) →  stock goes DOWN
        ↓
Manager catalog (/manage/catalog/)  →  read the joined picture
```

| This page **does** | This page **does not** |
|--------------------|------------------------|
| Show **active** items in **active** families | Show deactivated items, or items whose family is inactive |
| Show the **cached** on-hand quantity | Let you type a quantity (stock is a ledger — see [goods receipt](03-goods-receipts.md)) |
| Show buying + three selling prices | Let you change prices (use the [item console](01-items.md)) |
| Flag items at or below reorder | Raise a purchase order (use [purchase orders](02-purchase-orders.md)) |
| List suppliers that have a price for the item | Open a drawer or history |

Clicking a row does nothing — there is no detail drawer.

---

## 3. The console at a glance

> 📷 **[SCREENSHOT — manager catalog table, labelled]**

**A. Top bar**
- Title: **Manager catalog** (*Catálogo do gestor*)
- Signed in as *you@company*
- Language (English / Português), theme toggle, **Sign out**

**B. Toolbar (filters)**

| Control | EN | pt-PT | What it does |
|---------|----|-------|----------------|
| Search | *Search code or description…* | *Pesquisar código ou descrição…* | Filters as you type (internal code **or** description) |
| Family | *All families* | *Todas as famílias* | Restrict to one family |
| Checkbox | **Below reorder only** | **Só abaixo do ponto de encomenda** | Hide items that are OK |

Filters combine. They run in the browser on the loaded list — you do not need to click Search.

**C. Table columns**

| Column | Meaning |
|--------|---------|
| **Code** | Internal code (or — if empty on a legacy row) |
| **Description** | What the item is |
| **Family** | Family name |
| **Unit** | Unit of measure |
| **Stock** | Cached on-hand quantity (from the stock ledger) |
| **Reorder** | Reorder level set on the item |
| **Buying** | Cost we pay — see §5 |
| **Retail / Wholesale / Special** | The three **manual** selling prices |
| **Suppliers** | Suppliers that have a price for this item; the **primary** is marked ★ |
| **Status** | **Below reorder** (warning pill) or **OK** |

Rows at or below reorder are highlighted (warning styling) as well as the Status pill.

---

## 4. Stock and “below reorder”

**Stock** is the same cached balance as everywhere else: goods receipts add, goods issues subtract, admin **Adjust stock** corrects. This page only **displays** it. If stock looks wrong, trust **Stock movements** on the [goods receipt console](03-goods-receipts.md) — that is the ledger.

**Below reorder** is true when:

- the item’s **reorder level is greater than zero**, **and**
- **stock ≤ reorder level**.

A reorder level of **0** means “no reorder trigger” — the status stays **OK** even if stock is 0.

Use **Below reorder only** when you want a shortlist of items that need procuring.

---

## 5. Buying price and suppliers

Selling prices (retail / wholesale / special) are **manual** — they come from the item. Buying price is **dynamic** — it comes from the supplier price list.

The **Buying** column is one number per item:

1. If the item has a **primary** supplier (★) that is still active, that supplier’s cost is shown.
2. Otherwise the **cheapest** cost among **active** suppliers is shown.
3. If no active supplier has a price, Buying is **—**.

The **Suppliers** column lists names (comma-separated). Deactivated suppliers are omitted. **—** means no active supplier price yet — add one in the item console before you can raise a purchase order for that supplier.

Prices here are **not** a frozen PO snapshot; they follow the live supplier list. Approved purchase-order totals stay frozen on the PO — see [purchase orders](02-purchase-orders.md) §8.

---

## 6. Empty states and errors

| Message (exact, EN) | Why | What to do |
|---------------------|-----|------------|
| `No items to show.` | There are no active items in active families | Create/activate items in the [item console](01-items.md) |
| `No items match these filters.` | Search, family, or “below reorder only” hid every row | Clear search, set family to *All families*, untick the checkbox |
| `Could not load the catalog.` | The catalog API failed | Refresh the page; if it persists, ask an administrator |
| `The request could not be completed.` | A request failed without a specific message | Refresh; try again |
| `Catalogue view permission required` | You are not a warehouse user (typical for branch-only logins) | Use `/branch/catalog/` instead, or ask head office for a warehouse group |

The family dropdown can include **inactive** families (it reuses the families list). The table never lists items under an inactive family, so picking one of those families yields *No items match these filters.*

---

## 7. Related consoles

- [Item Console](01-items.md) — create/edit items, families, suppliers, selling prices, supplier prices.
- [Purchase orders](02-purchase-orders.md) — restock from suppliers when the catalog shows low stock.
- [Goods receipt & stock](03-goods-receipts.md) — book deliveries; that is what updates **Stock**.
- [Branches & Requisição interna](04-internal-requests.md) — branch catalogue (cost hidden) and the request / issue / receipt loop.
- [Edge cases, limits & troubleshooting](05-edge-cases-and-limits.md) — error messages and numeric bounds.
- [Admin & Superuser Reference](06-admin-reference.md) — who may use which URL.

---

## 8. Language, theme & dates

Same as the other warehouse consoles:

- **Language:** English / Português (top-right; remembered).
- **Theme:** light / dark (top-right; remembered).
- **Dates** are not shown on this page (no created/updated column). Quantity and money use a plain decimal format.

---

## 9. FAQ

**Q1. Why can’t I edit a price or the stock number here?**
This page is an overview. Change selling prices and supplier costs in the [item console](01-items.md). Change stock with a [goods receipt](03-goods-receipts.md) or (admin only) **Adjust stock**.

**Q2. Why is Buying “—” when I know we have a supplier?**
That supplier is **inactive**, or there is no supplier price for this item. Add an active supplier price in the item console (Suppliers → Supplier prices).

**Q3. What does the star (★) on a supplier mean?**
That supplier is the item’s **primary** (preferred). Its cost is the Buying figure. Only one primary per item.

**Q4. Why does this page show exact stock but the branch catalogue does not?**
Deliberate. Warehouse staff see the cached quantity here. Branch staff see only **In stock / Low / None** on `/branch/catalog/` — see [Branches & Requisição interna](04-internal-requests.md) §3.

**Q5. I deactivated an item and it vanished from this list — is it deleted?**
No. Deactivated items (and items whose family is inactive) are excluded from this view. Reactivate in the item console to bring them back.

**Q6. Stock is 0 but Status says OK — is that a bug?**
Not if **Reorder** is 0. A zero reorder level means “do not flag”. Set a reorder level greater than 0 on the item if you want the warning.

**Q7. I am a warehouse operator — should I see cost?**
Yes. Every warehouse group that can open this page sees buying price. Cost is hidden only on the **branch** catalogue.

**Q8. Can two items have the same internal code?**
No — codes are unique (case-insensitive) and stored **uppercase**. That rule is enforced in the item console, not here. See [Item Console](01-items.md) FAQ.
