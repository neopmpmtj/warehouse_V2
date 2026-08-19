# Product management console — session report

**Date:** 18 August 2026  
**App:** CentCompras (central warehouse + satellite branches)  
**Scope of this session:** product table foundation review, then a warehouse-staff **product management console** (front end + staff API), plus follow-up behaviour and correctness fixes.

Read this document first if you are resuming work on the staff product UI. The branch phone catalogue at `/` is a **different page** and was not redesigned here.

---

## 1. Who this is for

Anyone opening this repository after this session: a future agent, a developer who was not in the conversation, or the same people returning later without the chat history.

The conversation itself will not be available. This file is the handoff for **what was asked, what was decided, what was built, what broke, and what was deliberately left out**.

---

## 2. Business context (as stated in the session)

CentCompras is a logistics app for a **central warehouse**. Satellite companies (third parties or branches) place orders/requests against that warehouse.

The foundation of ordering is a list of **available products**. “Available” is **not** “has stock”. Availability is decided by **filters** (active catalogue, family, and so on), regardless of stock quantity. Stock is a number shown on the product; it does not hide the row by itself.

If a product does not exist in the catalogue, it will later be requested through another API/function. That path does not exist yet. For it to exist later, the product table and its related tables must already be solid.

Warehouse staff (`User.is_staff`, seeded as `warehouse@centcompras.dev`) manage the catalogue. Branch users only browse. This session was **not** about branches, tenancy, or orders. It was about the **product app**: the product table, foreign-key related tables, and a way for warehouse staff to see and change records without living in Django admin.

The requester described a short attention span and a need to **visualise** the table (filter, click, edit, save) so missing pieces become obvious. The console was requested for that reason: a hosted page in the Django app, not a Cursor canvas and not a new SPA framework.

---

## 3. What already existed before this session

The product domain was already implemented in PostgreSQL via Django:

| Model | Role |
|-------|------|
| `Product` | Master catalogue row (global; **no** `branch_id`) |
| `ProductFamily` | Required FK on every product (`PROTECT` on delete) |
| `Supplier` | Supplier master |
| `ProductSupplier` | Many-to-many link (product ↔ supplier), unique pair |
| `ProductChangeLog` | Immutable audit (who, action, field diffs, optional `reason`, when) |

**Product fields:** `family`, optional unique `internal_code`, `description`, `stock` (decimal), `price` (USD, decimal), `unit_of_measure`, `reorder_level`, `is_active` (soft delete), `created_at`, `updated_at`.

**Mutations** already went through `products/services.py` (`create_product`, `update_product`, `deactivate_product`, `reactivate_product`). Django admin for staff already used that layer. Branch API `GET /api/products/` returned **active products only**. CLI `add_product` remained for bootstrap.

Warehouse staff had **no branch membership**. `ActiveBranchMiddleware` therefore sent them to “no branch access” for any path that was not `/admin/`, `/accounts/`, or `/static/`. In practice they could only manage products in Django admin.

---

## 4. Original request (this session)

### 4.1 Foundation review

Assess the product table and FK-linked tables. Recommend anything that should be decided **now** to avoid painful later rewrites, **except** images and extra text/numeric columns (those can be added later easily).

Editing, changing, soft-delete, and adding products already existed. The question was: is the schema enough?

### 4.2 Staff management console

Build a **page hosted on the app** — a tables management console / dashboard — for the **product table**.

User for now: `warehouse@centcompras.dev`, authorised because `is_staff` is true.

Required behaviour:

- Visualise products in a console/dashboard.
- Filter products.
- Edit and delete (soft delete) per row, **or** checkboxes plus a dropdown of bulk actions (edit, delete, and future actions).
- Interactive: click, edit, save, using **existing business logic** (`services.py`), not a second mutation path.
- Bilingual UI: **English** and **Portuguese from Portugal** (`pt-PT`), including error messages.
- Instant **theme switching**.
- Not fancy. Prefer **HTML and JavaScript**. Tailwind had been “enough” in a previous project; speed was not a priority (~500 users). The site must still talk to database records.

Absolute project constraints that still applied: no React/Vue, no Django REST Framework unless later required, PostgreSQL is source of truth.

---

## 5. Foundation recommendations (discussed and agreed)

These were given before/alongside building the console. The requester **agreed** with the two locked decisions.

### 5.1 Locked now

1. **`is_active` means “in the available catalogue”** (soft delete / not listed for branches). It does **not** mean “has stock”. Availability is a filter. If a later phase needs “discontinued” vs “temporarily not sellable”, that is a **new flag**. Do not overload `is_active`.

2. **UI language is not product language.** The console is bilingual. Product `description` (and other catalogue text) stays **one field, one language** in the database. A `ProductTranslation` table can be added later without rewriting `Product`. Do not bilingualise product data in this phase.

### 5.2 Not added (easy or belongs elsewhere)

| Topic | Why it can wait |
|-------|-----------------|
| Images | Explicitly deferred. |
| Barcode / EAN, VAT, warehouse bin, extra numeric/text columns | Simple fields; add when needed. |
| Bilingual product descriptions | New translation table later; do not mix with UI i18n. |
| Audit tables for Family and Supplier | Product has `ProductChangeLog`. Family/Supplier mutations currently log to files only. Add when those entities get their own consoles. |
| Price/description snapshot on orders | Belongs to the **orders** app, not Product. |
| Default/preferred supplier | `ProductSupplier` already allows many suppliers; `is_preferred` can be added on the link table later. |
| Family/supplier CRUD inside the product console | Product form uses existing families/suppliers as dropdowns/checkboxes. Creating a new family still uses Django admin in this phase. |

### 5.3 Schema already in good shape

The product graph was judged sufficient to build on: family, unit of measure, reorder level, suppliers, changelog, soft delete, unique internal code when set, `PROTECT` on family and changelog so products are not hard-deleted out from under history.

---

## 6. Tech stack chosen — and why

The requester asked for HTML/JS, mentioned Tailwind as past experience, required bilingual UI and instant theme switch, and did not need a high-performance SPA.

| Layer | Choice | Why |
|-------|--------|-----|
| Page | Django template `product_console.html` | Hosted on the app; login/session/CSRF already exist. |
| Behaviour | Plain JavaScript (`console.js`, `console_i18n.js`) | Project rule and requester preference: no React/Vue. One concept, readable for learning. |
| Styling | Hand-written CSS + **CSS custom properties** (`console.css`) | Instant light/dark by toggling `data-theme` on `<html>`. No Tailwind CDN (no extra dependency, no network requirement for staff console, theme variables are simpler than Tailwind `dark:` for this). Visual style is a dense operations table, not a marketing site. |
| i18n | Client-side dictionaries in `console_i18n.js` (`en` and `pt-PT`) | Instant language switch **without reload**. Django gettext would be correct for server-rendered chrome, but almost all strings are built in JS (table, toasts, dialogs). `localStorage` key `cc-lang`. Portuguese copy uses European forms (e.g. Guardar, Terminar sessão, Desativar), not Brazilian. |
| Theme | `data-theme="light"` / `"dark"` + `localStorage` `cc-theme` | Applied in a tiny blocking script in `<head>` to reduce flash. Toggle is instant. |
| Staff API | Django views + `JsonResponse` (no DRF) | Matches existing `GET /api/products/`. Mutations call `products/services.py` only. |
| Authz | `can_manage_catalog` = authenticated + `is_staff`; `staff_required` decorator | Same rule as Django admin for products. Branch roles do **not** grant catalogue edit. |
| Offline | **Not** used for this console | Branch catalogue uses Service Worker + IndexedDB. Staff management is online-only. Console assets are **not** in the app-shell cache list. |

Tailwind was considered (requester had used it). It was **not** adopted: the project forbids unnecessary frontend frameworks/tooling, 500 users do not need a utility CDN, and CSS variables implement instant theme more directly.

---

## 7. What was built

### 7.1 Page

- **URL:** `/manage/products/` (name: `product_console`)
- **Login:** `warehouse@centcompras.dev` / `devpass123` (after `./scripts/seed_dev_data.sh`) is redirected here after login because they are staff.
- **Layout:** sticky header (user, language, theme, sign out); toolbar (search, family, status, unit, “below reorder level”, bulk action + Apply, New product); table; right-hand **drawer** for create/edit; modal for deactivate reason; toast banner.

Table columns: checkbox, internal code, description, family, stock (with a “Low” pill when stock ≤ reorder level and reorder > 0), unit, reorder, price, suppliers, status, row actions (Edit, Deactivate/Reactivate).

Clicking a row opens the drawer. Checkboxes are for bulk deactivate/reactivate only (bulk **edit** of different values was not implemented).

### 7.2 Staff JSON API (under `/api/` because `products/urls.py` is mounted there)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/manage/products/` | All products (including inactive) + families + suppliers + unit choices |
| POST | `/api/manage/products/` | Create |
| GET/PATCH | `/api/manage/products/<id>/` | Read one / update fields + supplier ids |
| POST | `/api/manage/products/<id>/deactivate/` | Soft delete (**reason required**) |
| POST | `/api/manage/products/<id>/reactivate/` | Restore (reason still optional) |
| POST | `/api/manage/products/bulk/` | `action`: `deactivate` or `reactivate`; `ids`; reason required for deactivate |
| GET | `/api/manage/products/<id>/history/` | `ProductChangeLog` entries |

Branch `GET /api/products/` is unchanged: active products only, small payload (`id`, `description`, `stock`, `price`, plus `catalog_updated_at`).

### 7.3 Permissions and middleware

- HTML: unauthenticated → login redirect; logged-in non-staff → **403**.
- JSON: unauthenticated → **401**; non-staff → **403**.
- `ActiveBranchMiddleware` exempts `/manage/` and `/api/manage/` so warehouse staff **without a branch** can use the console. `/` (branch catalogue) still requires a branch.
- No-branch page shows a link to the console when `user.is_staff`.

### 7.4 Deactivate requires a reason (exception agreed in-session)

Create, update, and reactivate: `reason` remains **optional**.

Deactivate: **required** (non-empty after strip). Enforced in `deactivate_product` via `DeactivateReasonRequiredError`. The console shows a modal; if the drawer already has a reason for **that** product, that text is reused. Bulk deactivate always opens the modal. Django admin deactivate action uses an intermediate form with a required reason.

Already-inactive products: deactivate is a no-op and does not demand a reason.

### 7.5 Files added

| Path | Responsibility |
|------|----------------|
| `products/console_views.py` | Console page + staff JSON views |
| `products/templates/products/product_console.html` | Page shell |
| `products/static/products/css/console.css` | Layout, theme variables, `[hidden]` overrides |
| `products/static/products/js/console_i18n.js` | `en` / `pt-PT` strings |
| `products/static/products/js/console.js` | Fetch, table, filters, drawer, bulk, theme/lang |
| `products/templates/admin/products/deactivate_reason.html` | Admin bulk-deactivate reason form |

### 7.6 Files changed (non-exhaustive)

- `products/urls.py`, `products/web_urls.py` — routes
- `products/permissions.py` — `staff_required`
- `products/services.py` — deactivate reason; `set_product_suppliers`; create/update accept `supplier_ids` in the **same** atomic block; `select_for_update` on every real update
- `products/admin.py` — deactivate action asks for a reason
- `branches/middleware.py` — exempt manage paths
- `accounts/views.py` + `accounts/urls.py` — staff login lands on the console
- `branches/templates/branches/no_branch_access.html` — staff link
- `products/tests.py` — console, reason, rollback, supplier-only update
- `README.md`, `AGENTS.md`, seed command messages — handoff text

Django admin for products **remains**. The console is the staff-facing day-to-day UI; admin is still valid.

---

## 8. Data flow (keep this picture)

```text
Staff browser  (/manage/products/)
    → GET/POST/PATCH /api/manage/products/…
        → console_views.py  (thin: parse JSON, staff_required)
            → products/services.py  (rules, audit, transactions)
                → models.py
                    → PostgreSQL
```

The console does **not** write IndexedDB. IndexedDB is only the branch phone catalogue cache.

```text
Branch phone  (/)
    → GET /api/products/   (active only)
        → IndexedDB cache if offline
```

---

## 9. UX and bugs fixed during the session

These were found by using the page, then fixed. Do not regress them.

### 9.1 Reason dialog (and drawer) visible on first load; Cancel did nothing

**Cause:** CSS `display: flex` / `display: grid` on `.drawer` and `.dialog` overrode the HTML `hidden` attribute, so overlays painted immediately. Cancel had no listeners until JS opened the dialog.

**Fix:** `.drawer[hidden], .dialog[hidden], .backdrop[hidden], … { display: none !important; }` in `console.css`.

If CSS looks stale in the browser, hard-refresh (Ctrl+Shift+R).

### 9.2 Toast “Bulk action completed” never disappeared

**Cause:** `showBanner` never scheduled a hide.

**Fix:** success and error toasts clear after **5 seconds** (`console.js`). A new banner resets the timer.

### 9.3 Bulk action dropdown stayed on “Reactivate” (or Deactivate) after Apply

**Cause:** After a successful bulk call, selection was cleared but `#bulk-action` was not reset.

**Fix:** set `bulk-action` value to `""` (label “Bulk action”) after success.

### 9.4 Create/update vs suppliers in two transactions

**Cause:** `create_product` / `update_product` each committed, then `set_product_suppliers` ran in another `@transaction.atomic`. `ATOMIC_REQUESTS` is off. Invalid supplier IDs returned 400 after the product (or field update) was already saved; the UI showed failure and diverged from the DB.

**Fix:** optional `supplier_ids` is applied **inside** `create_product` and `update_product`. Failure rolls back the whole operation. Tests: invalid supplier on create does not leave a product; invalid supplier on PATCH does not change description or links.

### 9.5 No row lock when PATCH only sends `supplier_ids`

**Cause:** `select_for_update()` lived inside `if fields:`. Supplier-only updates skipped the lock.

**Fix:** lock the product row for every real `update_product` (fields and/or suppliers), then apply changes.

### 9.6 Reactivate sent a stale drawer reason to the audit log

**Cause:** In `toggleLifecycle`, deactivate called `resolveDeactivateReason` (drawer text only if the drawer is open **for that product**, otherwise the reason dialog). Reactivate skipped that check and always sent `document.getElementById("field-reason").value`. That input lives in the drawer form: it can be hidden, leftover from a previous edit, or belong to a different product. Reactivate is optional-reason, so leftover text still became `ProductChangeLog.reason`.

**Fix:** `reasonFromOpenDrawer(product)` returns the trimmed field only when the drawer is open and `state.editingId === product.id`. Reactivate uses that (empty otherwise). Deactivate still falls back to the modal when the drawer has no reason for that product.

**Not changed in the same pass:** bulk **reactivate** in `applyBulk` still reads `#field-reason` unconditionally. Bulk deactivate already ignores the drawer and always opens the modal.

---

## 10. How to run and practise

```bash
source .venv/bin/activate    # or: .venv/bin/python …
python manage.py migrate
./scripts/seed_dev_data.sh
python manage.py runserver
```

Use **one** host: `http://127.0.0.1:8000` **or** `http://localhost:8000`, not both (Service Worker for the branch app is origin-specific).

| Who | URL | Expect |
|-----|-----|--------|
| `warehouse@centcompras.dev` | `/manage/products/` after login | Console; all products including inactive |
| Same user | `/` | Still “no branch” (no membership) — link to console |
| `admin.lisbon@centcompras.dev` | `/` | Read-only catalogue |
| Branch user | `/manage/products/` | 403 |

Password for seeded users: `devpass123`.

Tests:

```bash
.venv/bin/python manage.py test products
```

---

## 11. i18n and theme (implementation notes)

- Language: `localStorage["cc-lang"]` is `"en"` or `"pt-PT"`. Changing the header `<select>` re-renders labels, filters, table, and drawer without a server round-trip.
- Theme: `localStorage["cc-theme"]` is `"light"` or `"dark"`.
- API error bodies are mostly English. The deactivate-reason error includes `code: "deactivate_reason_required"` so the console can show the translated string.
- Product descriptions in the table are **not** translated.

---

## 12. What this session did **not** do

- Orders app, cart, offline order queue.
- Family or supplier management consoles (admin only).
- Product images; extra catalogue fields.
- In-app branch switcher; Google OAuth.
- Caching the staff console in the Service Worker.
- Bulk **edit** of heterogeneous field values (only bulk deactivate/reactivate).
- Making deactivate reason required in the **drawer optional field** for Save — Save is still optional reason; only Deactivate is mandatory.

---

## 13. Suggested next steps (when visualising the console)

These came up as natural follow-ons, not built:

1. Same-style consoles for **ProductFamily** and **Supplier** (and then audit logs for those tables).
2. Whether **reactivate** should also require a reason (today: no).
3. Showing changelog field diffs more richly in the drawer (today: action, user, time, reason).
4. Then **orders**, using the existing global catalogue and branch-scoped order design in `docs/warehouse-tenancy-setup.md`.

---

## 14. Mental model — two UIs, one catalogue

| | Branch phone `/` | Warehouse console `/manage/products/` |
|--|------------------|--------------------------------------|
| User | Branch membership | `is_staff` |
| Products | Active only | Active and inactive |
| Mutate | No | Yes, via services + audit |
| Offline | Yes (SW + IndexedDB) | No |
| Languages | English page (not this session) | EN / pt-PT |

If a product is deactivated in the console with a reason, it disappears from `GET /api/products/` and therefore from the branch cache on the next successful fetch.

---

## 15. Pointers in the repo

- This file: `docs/product-console-session-2026-08-18.md`
- Project status: `README.md` → “Project status (handoff)”
- Agent short brief: `AGENTS.md`
- Incremental-build rules: `products/products_docs/aux_instructions.md`
- Order design (next major phase): `docs/warehouse-tenancy-setup.md`
