# Code Review — D37 branch commercial mode (priced vs unpriced)

> **Status (29 August 2026, 09:00 WEST):** **H1, M1, M2, L1–L3 applied** in the working tree. Original read-only findings follow; see **Resolution**.

**Date:** 2026-08-29  
**Repo:** `/home/pmpmt/python/260829-central_de_compras/warehouse_V2`  
**Scope:** company-wide unpriced / priced switch (`BranchCommercialSettings`, default unpriced). Branch catalogue + requisição + offline cache + warehouse Gross snapshot. Not Phase 7 deploy.

---

## Resolution (29 Aug 2026, later session)

| ID | Status | Summary |
|----|--------|---------|
| **H1** | Applied | Offline catalogue treats missing `meta.show_selling_prices` as unpriced (no inference from `retail_price`). `branch_catalog.js?v=4`; SW `centcompras-branch-v9`. Manual 04 Q16 EN+PT. |
| **M1** | Applied | `BranchMembership.__str__` restored on the model. |
| **M2** | Applied | Branch `GET …/history/` strips money keys when unpriced; PostgreSQL changelog unchanged. |
| **L1** | Applied | Manual 10 Q3 EN+PT distinguishes PO self-cap vs unpriced requisição. |
| **L2** | Applied | Priced others-within-cap + others-over-cap tests. |
| **L3** | Applied | Admin `save_model` → `set_branch_commercial_mode`. |

---

## How this review was done

| Reviewer | Scope | Method |
|----------|--------|--------|
| Bugbot ([review](c5ae7f2a-cf2e-4456-8e49-3db9ffecbdb4)) | Branch changes (committed + working tree) | Diff-based bug pass with D37 instructions |
| Parent (this document) | Same D37 surface | Independent read of services, APIs, JS/IndexedDB/SW, tests, manuals; every Bugbot finding re-checked against current code |

Disagreements: none on Bugbot’s two hits (both reproduced). Parent added three further items Bugbot did not report.

---

## Verdict: **APPLIED** (was: two to fix before relying on unpriced in the field)

The server-side split is sound: unpriced APIs omit selling prices and totals; EUR `BranchApprovalLimit` is skipped; `approve()` still snapshots `unit_price` / `approved_*` for warehouse Gross; wholesale `> 0` is still required; warehouse `/manage/…` is unchanged; SW cache `v8` and `?v=` bumps are in place.

Two real defects remain: **offline catalogue can still show selling prices after an unpriced deploy**, and **`BranchMembership.__str__` was indented into `Meta`**. A third hole: the branch **history** API still returns money in changelog `changes`.

| Count | Severity |
|-------|----------|
| 0 | Critical |
| 1 | High |
| 2 | Medium |
| 3 | Low |

---

## Findings (unified — act on these IDs)

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| H1 | High | `branches/static/branches/js/branch_catalog.js:31-37` | Offline path infers “show prices” from cached `retail_price` when `meta.show_selling_prices` is missing (pre-D37 IndexedDB) |
| M1 | Medium | `branches/models.py:62-63` | `BranchMembership.__str__` lives inside `Meta`; Django never calls it |
| M2 | Medium | `orders/console_views.py:332-336` + `orders/services.py:497-508,709-721` | `GET /api/branch/requests/<id>/history/` still returns `unit_price` / `approved_*` to branch users in unpriced mode |
| L1 | Low | `docs/user-manuals/en/10-approval-limits.md` §6 Q3 (and pt) | FAQ still says a branch request is always capped by self-approve EUR |
| L2 | Low | `orders/tests.py:158-163` | `test_manager_approves_others_within_cap` no longer exercises a cap (default is unpriced); no priced others-over-cap test |
| L3 | Low | `branches/admin.py:21-31` | Admin save writes the singleton directly; bypasses `set_branch_commercial_mode` (no `logger.info`) |

---

## Comparison

| Finding | Bugbot | Parent | Resolution |
|---------|--------|--------|------------|
| Offline price inference | High | Confirmed | **H1** — real leak on first offline visit after deploy, or any failed catalog fetch while legacy cache remains |
| `BranchMembership.__str__` in `Meta` | Medium | Confirmed from the diff (indent accident while inserting `BranchCommercialSettings`) | **M1** |
| History API money | — | Found | **M2** — list/detail omit money; history was not updated. UI does not call it; the URL is listed on the warehouse dashboard |
| Manuals Q3 / tests / admin log | — | Found | **L1–L3** |

Not treated as findings (checked, working as designed):

- `/api/branch/catalog/` omits `retail_price` / `wholesale_price` / `special_price` in unpriced; cost and exact qty never present.
- Branch list/detail/create/line APIs omit `unit_price`, `vat_rate`, `totals`, `approved_*` when unpriced; include them when priced.
- `_assert_can_approve` returns early when unpriced; `test_unpriced_manager_approves_over_self_cap` covers it; priced self-cap still tested.
- `approve()` still refreshes wholesale and freezes `approved_net/vat/gross`; warehouse `_serialize_warehouse_request` still sends Gross.
- `_ensure_wholesale_positive` still runs on add/submit/approve (unpriced is quantity-only in the UI, not “free items”).
- `branch_requests.js` offline mode uses `meta.show_selling_prices === true` only — missing flag means **hide** money (safe). Catalog.js is the unsafe twin.
- `saveCatalog` clears IndexedDB items then writes the live payload + boolean meta; after one successful fetch, unpriced cache has no price fields.
- Templates no longer hard-code Retail / Unit price columns; SW `centcompras-branch-v8`; `?v=` bumped on `branch_catalog.js`, `db.js`, `branch_requests.js`.
- `/manage/branch-approval-limits/` remains editable in unpriced (caps stored, not applied) — documented in manuals 04 / 10 / 06.
- `vat_rate` remains on the unpriced catalog JSON (not rendered). Not a selling price; left as a nit, not an ID.

---

### H1 — Offline catalog infers selling prices from cache

**Evidence.** Online path uses `data.show_selling_prices === true` and persists that boolean. Offline `loadFromCache` does not:

```31:37:branches/static/branches/js/branch_catalog.js
    function showSellingPricesFrom(rows, meta) {
        if (meta && typeof meta.show_selling_prices === "boolean") {
            return meta.show_selling_prices;
        }
        var row = rows && rows[0];
        return !!(row && Object.prototype.hasOwnProperty.call(row, "retail_price"));
    }
```

Pre-D37 IndexedDB rows have `retail_price` and **no** boolean meta. After deploy the company default is **unpriced**. If the network fetch fails (or the user never comes online), `loadFromCache` paints Retail / Wholesale / Special from the old cache.

The same window exists after a live switch priced → unpriced if the tablet is offline before the next successful catalog GET. `branch_requests.js` does **not** share this fallback (`showSellingPrices = !!(data.meta && data.meta.show_selling_prices)`), so the leak is catalogue-only.

**Why it matters.** D37’s promise is that unpriced branches do not see selling prices. The first days after deploy (and any later fetch failure against a still-priced cache) break that on the page staff actually browse.

**Fix:** if `meta.show_selling_prices` is not a boolean, treat it as **false**. Do not infer from item keys. Safer default matches company default (unpriced). Priced-mode tablets with a pre-D37 cache hide columns until they fetch once — acceptable.

**Tests / smoke:** seed IndexedDB catalog items that include `retail_price` and meta **without** `show_selling_prices`; load `/branch/catalog/` offline in unpriced — columns must not appear. Then online fetch — meta boolean written; second offline load still unpriced.

---

### M1 — `BranchMembership.__str__` nested in `Meta`

**Evidence.** The D37 diff moved the existing method into `Meta` while inserting `BranchCommercialSettings`. Current tree:

```53:63:branches/models.py
    class Meta:
        ordering = ["branch__name", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "branch"],
                name="unique_branch_membership_user_branch",
            ),
        ]

        def __str__(self):
            return f"{self.user.email} @ {self.branch.name} ({self.role})"
```

Django never uses `Meta.__str__`. Admin dropdowns, logs, and `str(membership)` fall back to `BranchMembership object (pk)`.

**Why it matters.** Cosmetic, but it is a regression from this exact edit and will confuse `/admin/` Branch memberships (the screen superusers actually use).

**Fix:** dedent `__str__` back onto `BranchMembership` (same indent as the fields). Leave `BranchCommercialSettings.__str__` where it is.

---

### M2 — Branch history API still returns money

**Evidence.** `_serialize_request` / `_serialize_line` honour `branch_shows_selling_prices()`. `request_history` dumps changelog `changes` as stored:

```332:336:orders/console_views.py
def request_history(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    return JsonResponse(
        {"history": [_serialize_history(log) for log in get_request_history(req)]}
    )
```

`add_line` logs `"unit_price": str(line.unit_price)`; `approve` logs `approved_net` / `approved_vat` / `approved_gross`. Any member of the branch can `GET /api/branch/requests/<id>/history/` (`@active_branch_required` only). The warehouse dashboard lists that URL. `branch_requests.js` does not call it.

**Why it matters.** Unpriced list/detail hide wholesale; history is a side door to the same snapshot. Not a UI leak today; it contradicts the D37 API contract.

**Fix:** strip money keys from `changes` when serializing for the branch (or omit `changes` entirely in unpriced). Keep full history for warehouse/admin. Do not change what PostgreSQL stores.

---

### L1 — Approval-limits FAQ still implies EUR always

**Evidence.** Manual 10 §4 was updated for unpriced. §6 Q3 (EN and PT) still says a person may approve their own **request** only up to the self-approve cap. That is true for POs and for **priced** requisição; false for default unpriced.

**Fix:** one sentence on Q3: branch requests have no euro cap unless priced mode is on.

---

### L2 — Priced others-cap untested

**Evidence.** `test_manager_self_approval_cap` now sets priced mode (correct). `test_manager_approves_others_within_cap` does not, so with default unpriced it only proves a manager can approve — not that the others cap fires. There is no `ApprovalLimitExceededError` test for a branch manager.

**Fix:** set priced in the within-cap test; add an over-cap others case.

---

### L3 — Admin flip is not logged

**Evidence.** Superuser `/admin/` saves `BranchCommercialSettings` via the model. `set_branch_commercial_mode` (used by tests) emits `logger.info`. Admin does not.

**Fix:** `save_model` → `set_branch_commercial_mode(form.cleaned_data["mode"])`, or accept that `/admin/` is the only writer and add a changelog later. Not blocking.

---

## Suggested apply order

1. **H1** — default offline catalogue to unpriced when the meta flag is absent.  
2. **M1** — restore `BranchMembership.__str__`.  
3. **M2** if you want the branch API contract airtight.  
4. **L1–L3** with manuals/tests/admin as convenient.

Do not treat leftover Phase 6 / chrome / threads nits as part of this queue.
