---
name: Catalog sort inactive
overview: Three manager-catalog tweaks — clickable column sorting, an opt-in Include inactive filter, and Suppliers listed with the primary first.
todos:
  - id: include-inactive-api
    content: Wire include_inactive=1 on manage_catalog_list → get_catalog(active_only=False); add service/API tests
    status: completed
  - id: include-inactive-ui
    content: Toolbar checkbox, refetch, inactive row/status, family (inactive) labels, i18n
    status: completed
  - id: column-sort
    content: Sortable headers on all catalog columns, client-side sort matching item console
    status: completed
  - id: suppliers-primary-first
    content: Serialize/display catalog suppliers with primary first, then remaining by name; API test
    status: completed
  - id: docs-verify
    content: Bump ?v=, manuals EN+pt, node --check, products tests, browser check
    status: completed
isProject: false
---

# Manager catalog: sort + include inactive + primary first

Three UI enhancements on [`/manage/catalog/`](products/templates/products/catalog.html). The page stays **read-only**. Default view stays **active items in active families**.

## 1. Include inactive

Today [`get_catalog(active_only=True)`](products/services.py) already excludes deactivated items and items under inactive families. The catalog API hard-codes that flag:

```1212:1216:products/console_views.py
        queryset = get_catalog(
            active_only=True,
            family=family_id or None,
            sub_family=sub_family_id or None,
        )
```

The serializer already returns `is_active` and `family.is_active`. No schema change.

**Toolbar:** add a second checkbox next to **Below reorder only**: **Include inactive** / **Incluir inativos**. Default off. Filters still combine (client-side family / sub-family / search / below-reorder; this one also refetchs).

**API:** `GET /api/manage/catalog/?include_inactive=1` → `get_catalog(active_only=False)`. Any other value or omitted → current behaviour. Existing tests keep passing.

**When the box is ticked:**

- Deactivated items **and** items whose family is inactive appear.
- Family / sub-family dropdown labels use the item-console pattern: `Name (inactive)`.
- Row class `is-inactive` when the item **or** its family is inactive (styles already in [`console.css`](products/static/products/css/console.css)).
- **Status** pill: deactivated item → muted **Inactive** (overrides Below reorder / OK). Active item under an inactive family keeps Below reorder / OK; the family column carries the `(inactive)` tag.
- Toggling the checkbox **reloads** the API (inactive rows are not in the default payload).

Sub-family inactivity is unchanged (D16: no cascade; those items already show if the item and family are active).

## 2. Clickable column sorting

Copy the item-console pattern already in [`item_console.html`](products/templates/products/item_console.html) and [`console.js`](products/static/products/js/console.js) (`th-sortable` / `.sort-btn` / `aria-sort` / ▲▼). Sort CSS already lives in [`console.css`](products/static/products/css/console.css) (`?v=18` on this page).

All 15 columns are sortable, **client-side**, after the current filters:

- **Text** (`localeCompare`, current language): Code, Description, Family, Sub-family, Unit, Suppliers, Status
- **Numeric**: On hand, Reserved, Available, Reorder, Buying, Retail, Wholesale, Special (`null` buying price sorts as empty / last via a sentinel, not as 0)

Click toggles asc → desc on the same column; a new column starts **asc**. Default (no click) stays API order (`id`). Tie-break is `id`. First click on Status with include-inactive on sorts Inactive / Below reorder / OK by the **displayed** i18n label.

## 3. Suppliers column — primary first

The **Suppliers** cell is a comma-separated list; the primary is marked ★. The list today follows prefetch/`SupplierItemPrice` PK order, so the ★ name is often **not** first.

Fix in [`_serialize_catalog_item`](products/console_views.py): after filtering to **active** suppliers, sort so **`primary=True` is first**, then the rest by supplier name (`locale`-insensitive casefold). No primary (all secondary) → name order only. [`catalog.js`](products/static/products/js/catalog.js) `renderSuppliers` keeps joining in array order (no extra client shuffle). Column sort on Suppliers then naturally keys off “primary name first”.

Test: item with two active prices, primary created **second** → API `suppliers[0].primary` is true and `suppliers[0].name` is that supplier.

Manual §3 / §5: “the **primary** is listed first and marked ★”.

## Files

- [`products/console_views.py`](products/console_views.py) — parse `include_inactive`; sort catalog `suppliers` primary-then-name
- [`products/templates/products/catalog.html`](products/templates/products/catalog.html) — checkbox + sortable `<th>`s; bump `catalog.js` `?v=5` → `?v=6` and `catalog_i18n.js` `?v=7` → `?v=8`
- [`products/static/products/js/catalog.js`](products/static/products/js/catalog.js) — `includeInactive` state, refetch, sort helpers (mirror console.js), inactive row/status, family labels
- [`products/static/products/js/catalog_i18n.js`](products/static/products/js/catalog_i18n.js) — `includeInactive`, `statusInactive` / `inactive`, `sortBy` / `sortActiveAsc` / `sortActiveDesc`
- [`products/tests.py`](products/tests.py) — `get_catalog(active_only=False)` includes deactivated + inactive-family items; API default excludes them; `?include_inactive=1` includes them; page contains `include-inactive` and `th-sortable`; suppliers list is primary-first
- Manuals: [`docs/user-manuals/en/07-manager-catalog.md`](docs/user-manuals/en/07-manager-catalog.md) §3 toolbar + §3 status + suppliers order + FAQ Q5; [`docs/user-manuals/pt/07-manager-catalog.md`](docs/user-manuals/pt/07-manager-catalog.md); empty-state line in [`docs/user-manuals/en/05-edge-cases-and-limits.md`](docs/user-manuals/en/05-edge-cases-and-limits.md) §2.1 (and pt)

## Verification

- `.venv/bin/python manage.py test products --noinput`
- `node --check` on `catalog.js` / `catalog_i18n.js`
- Browser: `/manage/catalog/` as `armazem.admin@centcompras.dev` — sort Code / Available / Buying; tick Include inactive after deactivating a seed item (or use a fixture); confirm default view still hides it; pick a multi-supplier seed item and confirm the ★ name is first in **Suppliers**
