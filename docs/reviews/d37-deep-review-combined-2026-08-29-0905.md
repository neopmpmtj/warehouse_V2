# Deep Review — D37 branch commercial mode (combined)

> **Status (29 August 2026, 09:05 UTC):** Read-only second-pass review. **Verdict: merge-ready** — original H1/M1/M2/L1–L3 are fixed in commit `b08e837`; no new blocking defects found. **L4–L6 / N1–N2 applied** (29 Aug afternoon session).

**Resolution (29 Aug 2026, afternoon)**

| ID | Status | Summary |
|----|--------|---------|
| **L4** | Applied | Warehouse dashboard API blurb mentions priced-mode selling prices |
| **L5** | Applied | Branch dashboard card copy + `preferences_bar.js` EN/PT i18n |
| **L6** | Applied | `GET …/history/` includes `commercial_mode` / `show_selling_prices` |
| **N1** | Applied | Unpriced catalog JSON omits `vat_rate` |
| **N2** | Applied | `saveCatalog` strips price/vat keys when unpriced; SW `centcompras-branch-v10` |

**Date:** 2026-08-29  
**Branch:** `branch-catalog-no-price`  
**Commit:** `b08e837` — feat: implement branch commercial mode (D37)  
**Prior review:** [`d37-priced-unpriced-review-2026-08-29-0845.md`](d37-priced-unpriced-review-2026-08-29-0845.md) (Bugbot + parent; fixes marked applied)

---

## How this review was done

| Reviewer | Scope | Method |
|----------|--------|--------|
| **Prior session** | D37 surface + Bugbot | Diff review; H1–L3 identified and applied in same commit tree |
| **Security pass (this session)** | Authz, API leakage, offline cache, cross-branch | Independent trace of all branch price surfaces + `branch_shows_selling_prices()` gates |
| **Workflow pass (this session)** | Consistency across catalog / requisição / offline / caps / manuals | Cross-surface comparison + manual spot-check |
| **Parallel sub-agents** | Split security vs workflow | **Not run** — Cloud Agent quota blocked delegated review; split passes performed manually with the same rubrics |

**Tests run (this session):** `branches` + `orders` — **99 OK**.

---

## Executive summary

D37 is **sound and internally consistent**. The company-wide singleton `BranchCommercialSettings` (default **unpriced**) drives:

- Branch catalog API and UI (selling prices omitted unless priced).
- Branch requisição list/detail/line APIs (money fields omitted unless priced).
- Branch history API (money keys stripped from changelog `changes` when unpriced).
- Manager EUR caps skipped in `_assert_can_approve` when unpriced.
- Warehouse path unchanged (`approved_gross` still serialized for issue queue).

Offline JS now **defaults to hide prices** when `meta.show_selling_prices` is absent (fixes the pre-D37 IndexedDB inference bug). Service Worker bumped to `centcompras-branch-v9`; static `?v=` bumps present.

| Severity | Open from prior review | New this session |
|----------|------------------------|------------------|
| Critical | 0 | 0 |
| High | 0 (H1 fixed) | 0 |
| Medium | 0 (M1, M2 fixed) | 0 |
| Low | 0 (L1–L3 fixed) | 3 optional nits |
| Nit | — | 2 |

**Recommendation:** **Merge** `branch-catalog-no-price` to `main`. Optional nits below are polish only — not a pre-merge queue.

---

## Security & authorization pass

### Checked — working as designed

| Surface | Unpriced behaviour | Notes |
|---------|-------------------|--------|
| `GET /api/branch/catalog/` | No `retail_price` / `wholesale_price` / `special_price` | Cost and exact qty never present |
| Branch requisição APIs | No `unit_price`, `vat_rate`, `totals`, `approved_*` on list/detail/lines | Mode flags on every mutating response |
| `GET …/history/` | Money keys stripped from `changes`; DB changelog unchanged | Test `test_unpriced_history_omits_money` |
| Offline `branch_catalog.js` | `show_selling_prices === true` only; missing meta → hide columns | No inference from cached `retail_price` |
| Offline `branch_requests.js` | Same strict meta boolean for cached catalog | Pending-detail estimates only when priced |
| `approve()` server | Still snapshots wholesale + freezes `approved_*` | Branch UI does not expose in unpriced |
| Warehouse `/manage/internal-requests/` | `_serialize_warehouse_request` still sends `approved_gross` | Intentional |
| Mode toggle | Only superuser `/admin/` → `set_branch_commercial_mode` | No branch API to flip mode |
| Cross-branch | `active_branch_required` + `_get_request_or_404` isolation | Warehouse users get 403 on branch APIs without membership |
| Wholesale gate | `_ensure_wholesale_positive` on add/submit/approve | Unpriced is quantity-only in UI, not “free items” |

### Not vulnerabilities (documented / acceptable)

- **`vat_rate` on unpriced catalog JSON** — percentage, not a selling price; not rendered in branch UI. Left as nit **N1**.
- **IndexedDB item rows may retain price fields until next successful catalog fetch** after priced→unpriced — UI and meta flag hide them; manual 04 Q16 documents staff should reconnect once. DevTools can still read stale IDB — inherent offline trade-off. Nit **N2**.

---

## Workflow & consistency pass

### End-to-end flows (unpriced default)

```text
Catalog (no selling columns) → Draft requisição (qty only)
    → Submit → Manager approve (yes/no, no EUR cap)
    → Warehouse issue (sees approved_gross) → Branch receipt (no prices)
```

Priced mode restores selling columns, line unit prices, totals, approve confirmation with gross, and manager EUR caps — aligned with manuals 04 / 10 / 06 (EN + PT).

### Surfaces compared

| Surface | Priced / unpriced aware | Consistent |
|---------|-------------------------|------------|
| `/branch/catalog/` + API | Yes | ✅ |
| `/branch/requests/` + APIs | Yes | ✅ |
| Offline catalogue cache | Yes (`meta.show_selling_prices`) | ✅ |
| Offline draft queue | Yes | ✅ |
| `/branch/receipts/` | Never showed selling prices | ✅ (no change needed) |
| `/branch/threads/` | No prices | ✅ |
| `/manage/branch-approval-limits/` | Editable always; caps apply only in priced | ✅ (documented) |
| `/manage/catalog/` | Warehouse only; unchanged | ✅ |

### Manuals vs code

- Manual 04, 06, 07, 10, 05 (edge cases) — updated for D37.
- Manual 10 Q3 (EN + PT) — distinguishes PO self-cap vs unpriced requisição. **L1 fixed.**
- Manual 04 Q16 — offline cache + missing mode flag. **H1 doc fix.**

### Tests

- Unpriced/priced list, history, catalog API — covered.
- Priced self-cap, unpriced over-cap, priced others-cap — covered (`test_manager_others_approval_cap`). **L2 fixed.**

---

## Prior findings — verification

| ID | Original issue | Current code | Status |
|----|----------------|--------------|--------|
| **H1** | Offline catalog inferred prices from cached `retail_price` | `showSellingPricesFrom(meta)` requires `=== true` | **Fixed** |
| **M1** | `BranchMembership.__str__` inside `Meta` | Method on model body (`models.py` ~62) | **Fixed** |
| **M2** | History API leaked money in unpriced | `_strip_money_from_changes` + `include_money` flag | **Fixed** |
| **L1** | Manual 10 Q3 implied EUR always for requisição | Q3 updated EN+PT | **Fixed** |
| **L2** | Priced others-cap untested | `test_manager_others_approval_cap` | **Fixed** |
| **L3** | Admin bypassed `set_branch_commercial_mode` | `save_model` → service | **Fixed** |

---

## Optional follow-ups (not blocking merge)

**All applied 29 Aug 2026 (afternoon).**

| ID | Severity | Location | Issue | Suggested fix |
|----|----------|----------|-------|---------------|
| **L4** | Low | `products/templates/products/dashboard.html` ~200 | Branch catalog API blurb still says “cost hidden, stock hint” only | Add “selling prices only in priced mode (D37)” |
| **L5** | Low | `branches/navigation.py` ~26 | Dashboard card: “cost always hidden” — omits default unpriced selling hide | Extend desc string / i18n key |
| **L6** | Low | `orders/console_views.py` `request_history` | Response omits `commercial_mode` / `show_selling_prices` (other branch endpoints include them) | Add `_branch_mode_fields()` for consistency |
| **N1** | Nit | `branches/console_views.py` `_serialize_branch_item` | `vat_rate` still in unpriced JSON | Omit if you want minimal API surface; not a selling price |
| **N2** | Nit | Offline IndexedDB | Stale price keys in item rows until refresh after mode flip | Already documented Q16; optional: strip price keys in `saveCatalog` when `show_selling_prices` is false |

---

## Suggested apply order (if polishing after merge)

1. **L4** — warehouse dashboard API list (staff-facing doc in UI).  
2. **L5** — branch dashboard card copy.  
3. **L6** — API consistency for history endpoint.  
4. **N1–N2** — only if tightening API/offline hygiene.

Do **not** reopen Phase 6 / chrome / threads leftover nits as part of D37.

---

## Sign-off

| Question | Answer |
|----------|--------|
| Safe to merge D37 to `main`? | **Yes** |
| Must-fix before field unpriced rollout? | **None** |
| Prior review fully addressed? | **Yes** (verified in tree) |
| Second opinion (security) | No bypass found beyond documented offline IDB stale-data edge |
| Second opinion (workflow) | Priced/unpriced behaviour aligned across server, JS, offline, manuals |
