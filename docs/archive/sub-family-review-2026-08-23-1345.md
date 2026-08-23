# Sub-family stitch-in review

> **Status: CLOSED — all SF1–SF4 findings applied (23 Aug 2026).** Archived; see [`handoff.md`](../handoff.md) for the current state. Do not treat as a work queue. Slice plan: [`.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md`](../../.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md).

- **Date:** 23 August 2026, 13:45 WEST
- **Scope:** Sub-families catalogue slice — models, services, console API/UI, manager catalog, branch catalog, admin, seed/CLI, integration with PO / inventory / orders
- **Method:** Code review, JS state trace, full test suite (424 tests after fixes)

---

## Summary

The stitch-in matches the locked slice decisions. No high-severity defects (wrong FK persistence, 500 on normal console paths, permission bypass, or catalog/PO hiding items incorrectly). A small set of **Low** operational polish items was found and **fixed in this session** (see below).

| # | Severity | Area | Summary | Status |
|---|----------|------|---------|--------|
| SF1 | Low | Item console JS | `setLanguage()` did not refresh the sub-families drawer table | Fixed |
| SF2 | Low | Item console i18n | `inactive_sub_family` / `duplicate_sub_family_name` banners dropped the quoted name when mapped from API `code` | Fixed |
| SF3 | Low | Item console JS | Sub-family (and family) drawer **item count** stale after item create/update until drawer re-open | Fixed |
| SF4 | Low | Tests | PATCH family+sub-family mismatch, `sub_family_id: null` clear, `sub_families` in list payload untested | Fixed (+3 tests) |

**Not bugs (confirmed):** optional sub-family forever; D16 no cascade; catalog `active_only` on family only; PO/orders pickers gate on family activity; family change clears sub-family select; manager catalog clears stale sub-family filter on family change.

---

## SF1 — Sub-family drawer i18n on language switch

**Files:** `products/static/products/js/console.js` — `setLanguage()`

**Issue:** Switching EN ↔ pt-PT refreshed family and supplier drawer tables but not the sub-families drawer (pills, buttons, labels stale).

**Fix:** Call `renderSubFamilyTable()` from `setLanguage()`.

---

## SF2 — Error banners missing sub-family name

**Files:** `products/static/products/js/console.js` — `api()`; `products/static/products/js/console_i18n.js`

**Issue:** API returns exact server strings (e.g. `Cannot assign items to inactive sub-family 'Bags'.`) but console mapped `code` to shorter i18n without the name.

**Fix:** i18n templates use `{name}`; `apiErrorMessage()` extracts the quoted name from `payload.error` when present and substitutes into the localized string; EN falls back to server text when extraction fails.

---

## SF3 — Drawer item counts stale after item save

**Files:** `products/static/products/js/console.js` — `replaceItem()`

**Issue:** Creating or updating an item’s family/sub-family did not adjust `state.families[].item_count` / `state.subFamilies[].item_count` until the drawer was closed and re-opened (same class of bug for families).

**Fix:** `replaceItem()` bumps family and sub-family counts on create and on family/sub-family change; re-renders family and sub-family tables when counts change.

---

## SF4 — Missing API test coverage

**Files:** `products/tests.py` — `ItemConsoleTests`

**Added:**

- `test_item_patch_rejects_family_change_with_mismatched_sub_family`
- `test_item_patch_can_clear_sub_family_with_null`
- `test_manage_item_list_includes_sub_families`

---

## Verification

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput
```

**424 tests OK** after this review session (421 baseline + 3 new).

---

## Out of scope (locked slice)

Required sub-family, cascade deactivate, rename/move parent, N-level trees, branch-catalog sub-family filter — not implemented by design.
