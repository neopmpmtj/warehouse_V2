from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class VatRate(models.Model):
    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    rate = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        ordering = ["rate"]

    def __str__(self):
        return self.label


class FamilyProduct(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "family"
        verbose_name_plural = "families"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_familyproduct_name_ci",
            ),
        ]

    def __str__(self):
        return self.name


class ItemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Item(models.Model):
    class UnitOfMeasure(models.TextChoices):
        PIECE = "piece", "Piece"
        KG = "kg", "Kilogram"
        G = "g", "Gram"
        M = "m", "Meter"
        M2 = "m2", "Square meter"
        M3 = "m3", "Cubic meter"
        L = "l", "Liter"

    family = models.ForeignKey(
        FamilyProduct,
        on_delete=models.PROTECT,
        related_name="items",
    )
    internal_code = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255)
    unit_of_measure = models.CharField(
        max_length=16,
        choices=UnitOfMeasure.choices,
        default=UnitOfMeasure.PIECE,
    )
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        help_text="Cached stock balance — updated only via StockMovement.",
    )
    vat_rate = models.ForeignKey(
        VatRate,
        on_delete=models.PROTECT,
        related_name="items",
    )
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ItemQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("internal_code"),
                condition=~models.Q(internal_code=""),
                name="unique_item_internal_code_ci",
            )
        ]

    def __str__(self):
        if self.internal_code:
            return f"{self.internal_code} — {self.description}"
        return self.description


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_supplier_name_ci",
            ),
        ]

    def __str__(self):
        return self.name


class ItemChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DEACTIVATED = "deactivated", "Deactivated"
        REACTIVATED = "reactivated", "Reactivated"

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_change_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class FamilyChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DEACTIVATED = "deactivated", "Deactivated"
        REACTIVATED = "reactivated", "Reactivated"

    family = models.ForeignKey(
        FamilyProduct,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="family_change_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.family_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class SupplierChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DEACTIVATED = "deactivated", "Deactivated"
        REACTIVATED = "reactivated", "Reactivated"

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_change_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supplier_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class SupplierItemPrice(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="item_prices",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="supplier_prices",
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "item"],
                name="unique_supplier_item_price",
            ),
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(primary=True),
                name="unique_primary_supplier_item_price",
            ),
        ]

    def __str__(self):
        return f"{self.supplier.name} → {self.item} @ {self.cost_price}"


class SupplierItemPriceChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DEACTIVATED = "deactivated", "Deactivated"
        REACTIVATED = "reactivated", "Reactivated"

    supplier_item_price = models.ForeignKey(
        SupplierItemPrice,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_item_price_change_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supplier_item_price_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
