---
name: Fix H1 H2 H3
overview: Fix the three high-severity review findings (PO line race, inactive sessions, primary-supplier uniqueness), add targeted tests, run the full suite the fast way (~20s, not minutes), and mark H1–H3 done in the live review tracker.
todos:
  - id: h1-lock-po
    content: Lock PO in add_line / update_line / remove_line; add FOR UPDATE tests
    status: completed
  - id: h2-inactive
    content: Shared inactive-user guard in *_required decorators + accounts tests
    status: completed
  - id: h3-primary
    content: Partial unique index, lock item, clear-then-save primary; add tests + migration
    status: completed
  - id: fast-suite
    content: Run full suite with --keepdb --noinput; mark H1–H3 done in review tracker
    status: completed
isProject: false
---

# Fix H1–H3 and run tests fast

## Why tests were slow vs ~18–30s

The suite is already designed to be fast. Handoff: ~199 tests in ~18s. The 5-minute run is almost certainly **not** extra test logic — it is how Django talks to PostgreSQL.

| Slow path (2–3s per test) | Fast path (this project) |
|---|---|
| `TransactionTestCase` **flushes/recreates tables** between tests | Almost everything uses `django.test.TestCase` — wrap in a transaction and **rollback** |
| Recreating `test_centcompras_db` + running all migrations every invocation | `--keepdb` reuses the test database |
| Default PBKDF2 hasher (~870k iterations) on every `create_user` | [`config/settings.example.py`](config/settings.example.py) sets `TESTING` + `MD5PasswordHasher` when `test` is in `sys.argv` |
| Verbose log I/O | `logging_utils` skips file logs and raises console to WARNING under `TESTING` |

Only one class is legitimately slow: [`ConcurrentReceiptTests`](inventory/tests.py) (`TransactionTestCase`) — needed so two threads can see each other’s commits. That is **one** class, not all ~199 tests.

**How the other agent ran it fast:** `.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput`

First run after a new migration still migrates the test DB once; later runs skip CREATE DATABASE. Do **not** make H1/H3 tests inherit `TransactionTestCase` unless a true two-thread race is required. Prefer `TestCase` + `CaptureQueriesContext` (`FOR UPDATE`) like [`test_receive_goods_locks_rows_for_update`](inventory/tests.py), and add at most one `TransactionTestCase` per race (same pattern as inventory).

---

## H1 — Lock the PO on line mutations

**Bug:** [`add_line`](procurement/services.py) calls `_ensure_draft(po)` on an unlocked row. `update_line` / `remove_line` lock the **line** but not the **PO**. `submit()` / `approve()` already `select_for_update()` the PO, so a line can be saved after approval and break D13 snapshots.

**Fix in** [`procurement/services.py`](procurement/services.py):

- Helper `_lock_po(po)` → `PurchaseOrder.objects.select_for_update().get(pk=...)`
- `add_line`: lock PO first, then `_ensure_draft`
- `update_line` / `remove_line`: lock **PO first**, then line (same lock order as submit/approve to avoid deadlocks), then `_ensure_draft`

**Tests in** [`procurement/tests.py`](procurement/tests.py):

- `CaptureQueriesContext`: `add_line` / `update_line` / `remove_line` emit `FOR UPDATE` on `purchaseorder`
- Existing `test_lines_cannot_change_after_submit` still covers the sequential case
- Optional: one `TransactionTestCase` racing `add_line` vs `submit` (mirror inventory); keep it to a single test so the suite stays fast

---

## H2 — Reject inactive users with a live session

**Bug:** [`catalog_required`](products/permissions.py), [`procurement_required`](procurement/permissions.py), [`inventory_required`](inventory/permissions.py) check `is_authenticated` only. Django still loads an inactive user from an existing session. `/admin/` already requires `is_active`.

**Fix:** small shared helper (e.g. `accounts/authz.py`) used by all three `*_required` decorators, **after** the auth check and **before** permission checks:

- If `is_authenticated` and not `is_active`: `logout(request)` and return **403** JSON (`/api/`) or **403** HTML
- Also require `is_active` in `can_view_catalog` / `can_view_purchase_orders` / `can_view_inventory`

Login itself stays unchanged (inactive users cannot obtain a **new** session).

**Tests in** [`accounts/tests.py`](accounts/tests.py) (and a thin API check): warehouse user `force_login` → set `is_active=False` → GET `/api/manage/items/` and a staff page → 403; session cleared.

---

## H3 — One primary supplier price per item

**Bug:** “one primary per item” is Python-only. [`create_supplier_item_price`](products/services.py) **saves first, then** [`_clear_other_primaries`](products/services.py). Two concurrent `primary=True` writes can leave two primaries. A DB unique constraint would also break the current save-then-clear order **sequentially**.

**Fix:**

1. [`products/models.py`](products/models.py) — partial unique (same style as `unique_item_internal_code_ci`):

```python
models.UniqueConstraint(
    fields=["item"],
    condition=models.Q(primary=True),
    name="unique_primary_supplier_item_price",
)
```

2. Migration `products/0006_...` (generate with `makemigrations`).

3. [`products/services.py`](products/services.py) — when setting `primary=True`:
   - `Item.objects.select_for_update().get(pk=item.pk)` (serialize mutations)
   - **clear other primaries first**, then save the new/updated row as primary

**Tests in** [`products/tests.py`](products/tests.py):

- Existing `test_setting_primary_clears_other_primaries` must still pass (this is the order change)
- Constraint: two `primary=True` rows for the same item via ORM bypass → `IntegrityError`
- `CaptureQueriesContext` or one small `TransactionTestCase` for concurrent primary creates → exactly one `primary=True` at the end

---

## After tests pass

Update the tracker in [`docs/code-review-full-2026-08-20-2208.md`](docs/code-review-full-2026-08-20-2208.md): H1, H2, H3 → done. Leave M/L rows unchanged. Do not archive the doc (archive only when the whole backlog is done).

Run:

```bash
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```

Expect ~20–40s after the test DB exists; first run after the new migration is a bit longer (one migrate, not per-test recreate).
