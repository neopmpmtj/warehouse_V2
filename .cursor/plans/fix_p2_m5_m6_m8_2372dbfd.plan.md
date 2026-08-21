---
name: Fix P2 M5 M6 M8
overview: "Implement P2: DB-backed non-negative stock plus ledger=cache tests, deadlock-safe sorted item locks on multi-line receipts, exclusive warehouse group assignment with code-owned group perms. Leave M7 deferred. Then run the suite fast and mark M5/M6/M8 done."
todos:
  - id: m5-ledger-constraint
    content: CheckConstraint quantity >= 0; ledger_quantity helper; invariant tests
    status: completed
  - id: m6-sorted-locks
    content: Lock receipt items by sorted pk before writing movements; FOR UPDATE test
    status: completed
  - id: m8-exclusive-groups
    content: Exclusive assign_warehouse_group; document set(); accounts tests
    status: completed
  - id: p2-fast-suite
    content: Run full suite with --keepdb --noinput; mark M5/M6/M8 done (M7 stays deferred)
    status: completed
isProject: false
---

# Fix P2 (M5, M6, M8)

Same shape as [`.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md`](.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md) and P1: service-layer rules, `TestCase` tests, `--keepdb --noinput`, then tracker. Do **not** archive the review.

**Locked this session:**

- **M7:** skip — stay deferred. Pagination is additive later; doing it now without a dedicated frontend pass would break `loadCatalog()` dropdowns that assume all items in memory.
- **M8:** keep `permissions.set()` (code owns warehouse group perms) **and** make `assign_warehouse_group` exclusive. Document that extras added in `/admin/` are wiped on migrate.

Leave M1, M7, M10, L* untouched. M2–M4, M9, H1–H3 stay Done.

**Tests:** `.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput`. Prefer `TestCase`. Inventory already has one `TransactionTestCase` for over-receive; do **not** add another unless a lock-order test cannot be done with `CaptureQueriesContext`. If `--keepdb` is stale, recreate once without `--keepdb`.

---

## M5 — Ledger vs `Item.quantity` + non-negative DB check

**Bug:** [`Item.quantity`](products/models.py) is a cache of `Sum(StockMovement.quantity)` with no DB check. Negative balances are only blocked in [`_write_movement`](inventory/services.py). Drift from shell/SQL would go unnoticed; L14 called for a sum==quantity test when fixing M5.

**Fix:**

1. [`products/models.py`](products/models.py) — `CheckConstraint` on `Item`:

```python
models.CheckConstraint(
    condition=models.Q(quantity__gte=0),
    name="item_quantity_gte_zero",
)
```

Migration via `makemigrations` (products). Existing rows should already be ≥ 0; if migrate fails, stop and inspect — do not silently clamp.

2. [`inventory/services.py`](inventory/services.py) — helper `ledger_quantity(item)` → `StockMovement.objects.filter(item=item).aggregate(total=Sum("quantity"))` defaulting to `Decimal("0")`. Used by tests (and any future check command). **No new standalone script.** A tiny `manage.py check_stock` is optional and **out of scope** for this pass (enhancement #1).

3. Tests in [`inventory/tests.py`](inventory/tests.py): after `receive_goods` and after `adjust_stock`, `item.quantity == ledger_quantity(item)` (quantized to 3 dp). ORM/raw attempt to set `quantity=-1` raises `IntegrityError` (wrap in `transaction.atomic()`).

---

## M6 — Sorted item locks on multi-line receipt

**Bug:** [`receive_goods`](inventory/services.py) writes movements in payload order; each `_write_movement` `select_for_update()`s that item. Two receipts with overlapping items in opposite order can deadlock.

**Fix in** `receive_goods`, after `normalized` is built and **before** creating the `GoodsReceipt`:

```python
item_ids = sorted({po_line.item_id for po_line, _qty in normalized})
list(
    Item.objects.filter(pk__in=item_ids)
    .order_by("pk")
    .select_for_update()
)
```

Then the existing loop can still call `_write_movement` (second lock on the same rows in this transaction is fine). Same lock order everywhere: PO first (already), then items by `pk`.

**Tests:** extend [`test_receive_goods_locks_rows_for_update`](inventory/tests.py) (or add a sibling) with a **two-line** PO so `FOR UPDATE` hits `products_item` and the SQL includes `ORDER BY`. Sequential receive of two lines still updates both balances. No extra `TransactionTestCase`.

---

## M8 — Exclusive warehouse role + document `set()`

**Bugs:** [`assign_warehouse_group`](accounts/groups.py) only `groups.add()` — manager then operator keeps manager perms. [`sync_warehouse_groups`](accounts/groups.py) `permissions.set(desired)` wipes extras on migrate (keep this; it is the source of truth).

**Fix in** [`accounts/groups.py`](accounts/groups.py):

- Docstring on `sync_warehouse_groups`: warehouse group permission sets are fully managed in code; extras added in `/admin/` are replaced on migrate. Do not grant extra perms on these three groups.
- `assign_warehouse_group`: before `add`, remove other warehouse groups:

```python
user.groups.remove(
    *Group.objects.filter(name__in=WAREHOUSE_GROUP_NAMES)
)
user.groups.add(group)
```

Leave non-warehouse groups (if any) alone. Seed already calls `assign_warehouse_group` per user — exclusive assign makes re-seed safer.

**Tests in** [`accounts/tests.py`](accounts/tests.py):

- Assign `GROUP_MANAGERS` then `GROUP_OPERATORS` → user is only in operators; `has_perm(ADD_ITEM)` is False.
- Existing `test_assign_warehouse_group_preserves_extra_permission` still checks that **assign** does not strip extras on the **group** object (that test is about `user.groups.add`, not `sync`). Keep it.
- Optional: `sync_warehouse_groups()` after adding an extra perm to admins → extra is gone (documents `set()`). One test is enough.

---

## After tests pass

Update [`docs/code-review-full-2026-08-20-2208.md`](docs/code-review-full-2026-08-20-2208.md):

- M5, M6, M8 finding **Status** → Done (one line each).
- Tracker: those three → Done. **M7 stays deferred.**
- Do not archive.

Run:

```bash
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```
