# CentCompras — User Manual: Approval Limits

**The approval limits consoles** · Version 1.0 · For warehouse staff (admin / manager / operator)

> **Companion:** [Edge cases, limits & troubleshooting](05-edge-cases-and-limits.md) — the reference for error messages and numeric bounds. [Purchase orders](02-purchase-orders.md) — where the warehouse PO caps are applied. [Branches & requisição interna](04-internal-requests.md) — where the branch manager caps are applied. [Admin & Superuser Reference](06-admin-reference.md) — users, roles, permissions.

---

## Where do I go?

> **Open your browser and go to:**
>
> - **Warehouse PO caps:** **`https://<your-domain>/manage/approval-limits/`**
> - **Branch manager caps:** **`https://<your-domain>/manage/branch-approval-limits/`**
>
> *(During development on your own machine: `http://127.0.0.1:8000/manage/approval-limits/` and `http://127.0.0.1:8000/manage/branch-approval-limits/`)*

Sign in with your email + password (the one your administrator gave you). These consoles are **read-only for most staff** — only warehouse **admins** can change the caps (see §3).

---

## 1. What approval limits are

Approval limits are **monetary caps** (in **EUR, VAT included**) that control who may approve what:

| Cap | Applies to | Model |
|-----|-----------|-------|
| **Warehouse PO cap** | Approving a **purchase order** (`/manage/purchase-orders/`) | `ApprovalLimit` (group + grade → self/others) |
| **Branch manager cap** | Approving an **internal request** (`/manage/internal-requests/` + `/branch/…`) | `BranchApprovalLimit` (role `manager` → self/others) |

Every cap has **two values**:

- **Approve others** — the maximum gross amount a person may approve on a document **created by someone else**.
- **Self-approve** — the maximum gross amount a person may approve on a document **they created themselves**.

The **self** cap is always lower — you are not meant to approve your own work beyond small amounts.

---

## 2. The two consoles at a glance

### 2.1 Warehouse PO caps — `/manage/approval-limits/`

![Approval limits console](screenshots/06-approval-limits.png)

A table with one row per **group + grade**:

| Column | Meaning |
|--------|---------|
| **Group** | The warehouse group the cap applies to (e.g. `warehouse_managers`) |
| **Grade** | The grade within that group (managers: 1–3; operators: 1–2) |
| **Approve others** | Max gross (EUR) this grade may approve on **another user's** PO |
| **Self-approve** | Max gross (EUR) this grade may approve on **their own** PO |
| *(button)* | **Save** — writes your edits (admins only) |

The defaults are created automatically and never overwrite your edits:

| Group | Grade | Approve others | Self-approve |
|-------|:---:|---:|---:|
| `warehouse_managers` | 2 | € 5,000.00 | € 100.00 |
| `warehouse_managers` | 3 | € 50,000.00 | € 500.00 |

### 2.2 Branch manager caps — `/manage/branch-approval-limits/`

A single panel for the **one global manager cap**:

| Field | Meaning |
|-------|---------|
| **Others** | Max gross (EUR) a branch **manager** may approve on a request created by **someone else** |
| **Self** | Max gross (EUR) a branch manager may approve on a request **they created** |
| **Save** | Writes your edits (admins only) |

Default:

| Role | Approve others | Self-approve |
|------|---:|---:|
| `manager` | € 5,000.00 | € 100.00 |

**Branch admins have no cap (unlimited)** — there is no row for them. **Operators never approve.** These caps are **global across all branches** in this phase.

---

## 3. Your role — what you can do

| Role | See the caps | Edit the caps |
|------|:---:|:---:|
| **Admin** (`warehouse_admins`) | ✅ | ✅ |
| **Manager** (`warehouse_managers`) | ✅ | ❌ |
| **Operator** (`warehouse_data_operators`) | ✅ | ❌ |

- Everyone with warehouse access can **view** both consoles.
- Only warehouse **admins** can change limits — the inputs are disabled for everyone else, and the API rejects edits with: *"Only warehouse admins can change approval limits."*
- In Django `/admin/` these tables are **read-only** — day-to-day changes go through these two consoles (which write the audit trail).

---

## 4. How the caps are applied

**Purchase orders (warehouse PO caps):**

- Manager **grade 1**: cannot approve at all.
- Manager **grade 2+**: may approve a PO when the **gross total** is within their cap — `Approve others` for someone else's PO, `Self-approve` for their own.
- **Admins** approve any amount.

**Internal requests (branch manager caps):**

- A branch **manager** may approve a request within the global manager cap — `Others` for requests created by other users, `Self` for their own.
- Branch **admins**: unlimited. **Operators**: never approve.

If a document is over the cap, you'll see an error like:

- *"Approval is limited to € … gross (this PO is …)."* — over your **others** cap → ask a higher-grade approver.
- *"Self-approval is limited to € … gross …"* — over your **self** cap → ask someone else to approve.
- *"No approval limit is configured for this grade."* — a missing `ApprovalLimit` row → ask a warehouse admin to set it.

---

## 5. History (audit trail)

Every change to a limit is recorded: **who** changed it, **when**, and the **old → new** values, in the `ApprovalLimitChangeLog` / `BranchApprovalLimitChangeLog` tables. These logs are read-only everywhere — they are the audit trail.

---

## 6. FAQ

**Q1. I see the caps but the fields are greyed out — why?**
Only warehouse **admins** can edit approval limits. If you're a manager or operator, the consoles are view-only by design.

**Q2. What does "gross" mean here?**
The **gross** total = net + VAT — the full amount to fund. Caps are checked against gross, VAT included.

**Q3. Can I approve my own purchase order / request?**
Only up to your **self-approve** cap (€ 100 / € 500 by default). Above that, another approver must approve it.

**Q4. I changed a value but it reverted / shows an error — why?**
Values must be **zero or greater**, with at most **2 decimal places**. Negative values are rejected. Also check the banner at the top of the console for the exact message.

**Q5. We changed the caps — will the defaults come back?**
No. Defaults are only created **when a row is missing**; they never overwrite your edits.

**Q6. Are branch caps per branch or global?**
**Global** in this phase — one manager cap applies to all branches. Per-branch caps may come later.
