# Warehouse App — Multi-Tenancy & Role Setup Instructions

**Status (18 August 2026):** `accounts` and `branches` from this document **are built**. The product catalogue is a separate, completed module (`products/`, staff console at `/manage/products/`).

**Do not implement §6–7 as written.** The `Order` example with `item_name` / `quantity` / `notes` was a placeholder from before `Product` existed. Branch orders are **on hold** until inbound stock can be recorded (warehouse purchases from suppliers → `Product.stock`). Order business rules (cart shape, stock decrement timing, cancel policy) are also not locked.

`User.is_staff` is **warehouse catalogue staff** (and Django admin), not “site admin only”. Site-wide config is `is_superuser`. Branch roles (`BranchMembership`) do **not** grant catalogue edit.

---

**Original context (kept for history):** Greenfield / early development. Database can be rebuilt from scratch — no data migration concerns. Existing functionality: a single "insert new row" feature (ID + 3 fields) to be replaced/extended by the `Order` model below.

**Stack:** Django, PostgreSQL, local dev on Ubuntu.

---

## 1. Overview

We are adding two things to the app:

1. **Multi-tenancy** — each `Branch` is a tenant. All order data is isolated per branch using a shared-table architecture (a `branch_id` foreign key on every business record — not separate databases or schemas).
2. **Custom user model** — login by **email + password** (no username field), with **role-based permissions scoped per branch** via a membership table.

### Roles (per branch)

| Role    | Create Order | Edit/Delete Order | Manage Branch Users |
|---------|:---:|:---:|:---:|
| Admin   | ✅ | ✅ | ✅ |
| Manager | ✅ | ❌ | ❌ |
| User    | ✅ | ❌ | ❌ |

- A user's role is **not global** — it's attached to their membership in a *specific* branch. A user can belong to multiple branches with a different role in each (e.g. a regional manager).
- Orders belong to exactly one branch. A branch only manages its own orders — no cross-branch ordering.
- None of these roles are Django superuser. Django's built-in `is_superuser` stays reserved for site-wide `/admin/` configuration. **`is_staff` is warehouse catalogue staff** (`/manage/products/` and product admin), separate from this per-branch role system.

---

## 2. Step-by-step build order

Build in this order — each step depends on the previous one.

1. Create custom `User` model (email login, no username)
2. Update `settings.py` (`AUTH_USER_MODEL`), create custom `UserManager`
3. Create `Branch` model
4. Create `BranchMembership` model (user, branch, role)
5. Create `Order` model with `branch` FK
6. Create a tenant-scoping base manager/queryset for `Order`
7. Wire up permission checks in views (create/edit/delete)
8. Register everything in Django admin for manual testing
9. Run migrations, create a superuser, create test branches/memberships

---

## 3. Custom User model (email-only login)

Since this is greenfield, replace the default `User` model entirely with a custom one **before running your first migration** — swapping `AUTH_USER_MODEL` after tables exist is painful, but since the DB is being created from scratch, do it now.

**`accounts/models.py`**

```python
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # warehouse catalogue + Django /admin
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # no username field, nothing else required at createsuperuser time

    def __str__(self):
        return self.email
```

**`settings.py`**

```python
AUTH_USER_MODEL = "accounts.User"
```

> ⚠️ Set `AUTH_USER_MODEL` and run this app's first migration **before** any other app's migrations that reference `User` (e.g. `Order`, `BranchMembership`). If migrations already exist for the old default user, delete the SQLite/Postgres dev database and all existing migration files, then start fresh — this is safe since it's greenfield.

---

## 4. Branch (tenant) model

**`branches/models.py`**

```python
from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

---

## 5. BranchMembership (user ↔ branch ↔ role)

This is the bridge table. Role lives **here**, not on `User`.

**`branches/models.py`** (continued)

```python
from django.conf import settings


class BranchMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        USER = "user", "User"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="branch_memberships",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "branch"], name="unique_user_branch_membership"
            )
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.branch.name} ({self.role})"
```

One user can have multiple `BranchMembership` rows (one per branch), each with its own role. A user with zero memberships is logged in but has no access to any branch's data — that's expected for a freshly created account, not a bug.

---

## 6. Order model (tenant-scoped business data)

**Sketch only — do not copy this into an `orders` app.** CentCompras already has a global `Product` catalogue. A real order line would reference `Product` (and later snapshot description/price), not a free-text `item_name`. Branch orders wait until inbound stock exists so quantity is not ordered against an empty warehouse.

The queryset helpers (`for_branch`, `for_user_branches`) and the `branch` + `created_by` FKs are still the right tenancy idea when orders are designed for real.

**`orders/models.py`** (historical placeholder)

```python
from django.conf import settings
from django.db import models
from branches.models import Branch


class OrderQuerySet(models.QuerySet):
    def for_branch(self, branch):
        return self.filter(branch=branch)

    def for_user_branches(self, user):
        branch_ids = user.branch_memberships.values_list("branch_id", flat=True)
        return self.filter(branch_id__in=branch_ids)


class Order(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_created"
    )
    # --- replace these with your actual 3 existing fields ---
    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    # ----------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderQuerySet.as_manager()

    def __str__(self):
        return f"Order #{self.pk} ({self.branch.name})"
```

**Why `.for_user_branches(user)` matters:** always fetch orders through this method (or equivalent) in every view/API endpoint, rather than `Order.objects.all()`. This is the single point where tenant isolation is enforced — it's much harder to accidentally leak cross-branch data if every entry point goes through one filtered method instead of relying on each view remembering to filter manually.

---

## 7. Permission checks

Keep it simple with a small helper rather than a full permissions framework — you only have 3 roles right now.

**`branches/permissions.py`**

```python
from branches.models import BranchMembership


def get_membership(user, branch):
    return BranchMembership.objects.filter(user=user, branch=branch).first()


def can_create_order(user, branch):
    m = get_membership(user, branch)
    return m is not None and m.role in (
        BranchMembership.Role.ADMIN,
        BranchMembership.Role.MANAGER,
        BranchMembership.Role.USER,
    )


def can_edit_or_delete_order(user, branch):
    m = get_membership(user, branch)
    return m is not None and m.role == BranchMembership.Role.ADMIN


def can_manage_branch_users(user, branch):
    m = get_membership(user, branch)
    return m is not None and m.role == BranchMembership.Role.ADMIN
```

Use these at the top of every relevant view:

```python
from django.core.exceptions import PermissionDenied
from branches.permissions import can_edit_or_delete_order

def delete_order_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not can_edit_or_delete_order(request.user, order.branch):
        raise PermissionDenied
    order.delete()
    ...
```

---

## 8. Django admin (for manual testing)

**`branches/admin.py`**

```python
from django.contrib import admin
from .models import Branch, BranchMembership

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")

@admin.register(BranchMembership)
class BranchMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "branch", "role")
    list_filter = ("branch", "role")
```

**`orders/admin.py`**

```python
from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "created_by", "item_name", "quantity", "created_at")
    list_filter = ("branch",)
```

**`accounts/admin.py`**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    search_fields = ("email",)
```

---

## 9. Migration & setup commands

```bash
# From project root, with your venv active
python manage.py makemigrations accounts branches orders
python manage.py migrate
python manage.py createsuperuser   # will prompt for email + password only
python manage.py runserver
```

Then via `/admin`:
1. Create 2–3 `Branch` records.
2. Create a few `User` records (or via `createsuperuser`/signup flow).
3. Create `BranchMembership` rows linking users to branches with roles — including at least one user with memberships in **two** branches (to test the regional-manager-style case), with a different role in each if you want to confirm role isolation per branch.
4. Log in as each test user and confirm: they only see orders for branches they have a membership in, and create/edit/delete behavior matches their role per the table in Section 1.

---

## 10. Things intentionally left out (fine for now)

- No separate "regional" tenant tier — someone overseeing multiple branches is just multiple `BranchMembership` rows, not a new model.
- No schema-per-tenant or database-per-tenant — unnecessary at ~500 users; shared table + `branch_id` FK with an index is sufficient.
- No passwordless/magic-link login — plain email + password as specified.

---

## 11. Inbound stock (under discussion — not in this original brief)

This document designed **branch-scoped outbound orders**. The catalogue now exists, and **stock is still a field typed on `Product`**.

The intended next product-side slice (not built):

```text
Warehouse purchases from suppliers
    → a receipt is recorded (who, which supplier, which products, quantities)
    → Product.stock is updated from that receipt
    → branch orders come later, against that stock
```

Do not add an `orders` app in order to “have somewhere to put stock”. Stock in is not a branch order. Naming (`procurement`, `purchases`, `receiving`) and whether the first slice is a full purchase order or a goods-receipt-only record are **not locked**. Agree that slice before coding.

Keep catalogue identity (family, description, unit, price, `is_active`) in `products`. Keep movement of quantity in a dedicated app that calls `products/services.py` (or a new stock-adjustment helper there) so PostgreSQL stays the source of truth.
