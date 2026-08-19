from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied, ValidationError
from django.template.response import TemplateResponse

from .models import (
    FamilyChangeLog,
    FamilyProduct,
    Item,
    ItemChangeLog,
    Supplier,
    SupplierChangeLog,
    VatRate,
)
from .services import (
    DuplicateFamilyNameError,
    DuplicateInternalCodeError,
    DuplicateSupplierNameError,
    FamilyNameRequiredError,
    InvalidSupplierEmailError,
    SupplierNameRequiredError,
    create_family,
    create_item,
    create_supplier,
    deactivate_item,
    reactivate_item,
    update_family,
    update_item,
    update_supplier,
    validate_family_name_available,
    validate_internal_code_available,
    validate_supplier_name_available,
)


class ItemAdminForm(forms.ModelForm):
    audit_reason = forms.CharField(
        required=False,
        max_length=255,
        label="Reason (optional)",
        help_text="Optional note stored in the audit log for this change.",
    )

    class Meta:
        model = Item
        fields = (
            "family",
            "internal_code",
            "description",
            "unit_of_measure",
            "reorder_level",
            "vat_rate",
        )

    def clean_internal_code(self):
        internal_code = self.cleaned_data.get("internal_code", "")
        exclude_item_id = self.instance.pk if self.instance.pk else None
        validate_internal_code_available(
            internal_code,
            exclude_item_id=exclude_item_id,
        )
        return internal_code


class ItemChangeLogInline(admin.TabularInline):
    model = ItemChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class FamilyChangeLogInline(admin.TabularInline):
    model = FamilyChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SupplierChangeLogInline(admin.TabularInline):
    model = SupplierChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    form = ItemAdminForm
    list_display = (
        "id",
        "internal_code",
        "description",
        "family",
        "unit_of_measure",
        "reorder_level",
        "vat_rate",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "family", "unit_of_measure", "vat_rate")
    search_fields = ("internal_code", "description", "family__name")
    autocomplete_fields = ("family", "vat_rate")
    readonly_fields = ("is_active", "created_at", "updated_at")
    inlines = (ItemChangeLogInline,)
    actions = ("deactivate_items", "reactivate_items")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "family",
                    "internal_code",
                    "description",
                    "unit_of_measure",
                    "reorder_level",
                    "vat_rate",
                    "is_active",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Audit",
            {"fields": ("audit_reason",)},
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("family", "vat_rate")
        )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied

        reason = form.cleaned_data.get("audit_reason", "")

        try:
            if change:
                updated = update_item(
                    request.user,
                    obj,
                    reason=reason,
                    family=form.cleaned_data["family"],
                    internal_code=form.cleaned_data["internal_code"],
                    description=form.cleaned_data["description"],
                    unit_of_measure=form.cleaned_data["unit_of_measure"],
                    reorder_level=form.cleaned_data["reorder_level"],
                    vat_rate=form.cleaned_data["vat_rate"],
                )
                obj.pk = updated.pk
            else:
                created = create_item(
                    request.user,
                    family=form.cleaned_data["family"],
                    description=form.cleaned_data["description"],
                    unit_of_measure=form.cleaned_data["unit_of_measure"],
                    vat_rate=form.cleaned_data["vat_rate"],
                    internal_code=form.cleaned_data.get("internal_code", ""),
                    reorder_level=form.cleaned_data["reorder_level"],
                    reason=reason,
                )
                obj.pk = created.pk
        except DuplicateInternalCodeError as exc:
            raise ValidationError({"internal_code": exc.messages[0]}) from exc

        obj.refresh_from_db()

    def _lifecycle_reason_page(self, request, queryset, *, action_name, confirm_field, title, help_text, submit_label):
        return TemplateResponse(
            request,
            "admin/products/lifecycle_reason.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "queryset": queryset,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "title": title,
                "action_name": action_name,
                "confirm_field": confirm_field,
                "help_text": help_text,
                "submit_label": submit_label,
            },
        )

    @admin.action(description="Deactivate selected items")
    def deactivate_items(self, request, queryset):
        if request.POST.get("confirm_deactivate"):
            reason = request.POST.get("reason", "").strip()
            if not reason:
                self.message_user(
                    request,
                    "A reason is required to deactivate an item.",
                    messages.ERROR,
                )
                return None
            for item in queryset:
                deactivate_item(request.user, item, reason=reason)
            self.message_user(
                request,
                f"Deactivated {queryset.count()} item(s).",
            )
            return None

        return self._lifecycle_reason_page(
            request,
            queryset,
            action_name="deactivate_items",
            confirm_field="confirm_deactivate",
            title="Deactivate items",
            help_text="A reason is required to deactivate items. They will leave the catalogue.",
            submit_label="Deactivate",
        )

    @admin.action(description="Reactivate selected items")
    def reactivate_items(self, request, queryset):
        if request.POST.get("confirm_reactivate"):
            reason = request.POST.get("reason", "").strip()
            if not reason:
                self.message_user(
                    request,
                    "A reason is required to activate an item.",
                    messages.ERROR,
                )
                return None
            for item in queryset:
                reactivate_item(request.user, item, reason=reason)
            self.message_user(
                request,
                f"Reactivated {queryset.count()} item(s).",
            )
            return None

        return self._lifecycle_reason_page(
            request,
            queryset,
            action_name="reactivate_items",
            confirm_field="confirm_reactivate",
            title="Reactivate items",
            help_text="A reason is required to activate items. They will return to the catalogue.",
            submit_label="Reactivate",
        )


class SupplierAdminForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "name",
            "contact_name",
            "email",
            "phone",
            "notes",
            "is_active",
        )

    def clean_name(self):
        exclude_supplier_id = self.instance.pk if self.instance.pk else None
        return validate_supplier_name_available(
            self.cleaned_data.get("name", ""),
            exclude_supplier_id=exclude_supplier_id,
        )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    form = SupplierAdminForm
    list_display = (
        "name",
        "contact_name",
        "email",
        "phone",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "contact_name", "email", "phone", "notes")
    readonly_fields = ("created_at", "updated_at")
    inlines = (SupplierChangeLogInline,)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "contact_name",
                    "email",
                    "phone",
                    "notes",
                    "is_active",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied

        try:
            if change:
                update_supplier(
                    obj,
                    user=request.user,
                    name=form.cleaned_data["name"],
                    contact_name=form.cleaned_data["contact_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                    is_active=form.cleaned_data["is_active"],
                )
            else:
                created = create_supplier(
                    name=form.cleaned_data["name"],
                    contact_name=form.cleaned_data["contact_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                    is_active=form.cleaned_data["is_active"],
                    user=request.user,
                )
                obj.pk = created.pk
        except DuplicateSupplierNameError as exc:
            raise ValidationError({"name": exc.messages[0]}) from exc
        except SupplierNameRequiredError as exc:
            raise ValidationError({"name": exc.messages[0]}) from exc
        except InvalidSupplierEmailError as exc:
            raise ValidationError({"email": exc.messages[0]}) from exc

        obj.refresh_from_db()


class FamilyProductItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ("internal_code", "description", "unit_of_measure", "is_active")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FamilyProductAdminForm(forms.ModelForm):
    class Meta:
        model = FamilyProduct
        fields = ("name", "is_active")

    def clean_name(self):
        exclude_family_id = self.instance.pk if self.instance.pk else None
        return validate_family_name_available(
            self.cleaned_data.get("name", ""),
            exclude_family_id=exclude_family_id,
        )


@admin.register(FamilyProduct)
class FamilyProductAdmin(admin.ModelAdmin):
    form = FamilyProductAdminForm
    list_display = ("name", "item_count", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (FamilyProductItemInline, FamilyChangeLogInline)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "is_active",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied

        try:
            if change:
                update_family(
                    obj,
                    user=request.user,
                    name=form.cleaned_data["name"],
                    is_active=form.cleaned_data["is_active"],
                )
            else:
                created = create_family(
                    name=form.cleaned_data["name"],
                    is_active=form.cleaned_data["is_active"],
                    user=request.user,
                )
                obj.pk = created.pk
        except DuplicateFamilyNameError as exc:
            raise ValidationError({"name": exc.messages[0]}) from exc
        except FamilyNameRequiredError as exc:
            raise ValidationError({"name": exc.messages[0]}) from exc

        obj.refresh_from_db()


class _ReadOnlyChangeLogAdmin(admin.ModelAdmin):
    list_filter = ("action",)
    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ItemChangeLog)
class ItemChangeLogAdmin(_ReadOnlyChangeLogAdmin):
    list_display = ("id", "item", "user", "action", "reason", "created_at")
    search_fields = (
        "item__description",
        "item__internal_code",
        "user__email",
        "reason",
    )
    readonly_fields = ("item", "user", "action", "reason", "changes", "created_at")


@admin.register(FamilyChangeLog)
class FamilyChangeLogAdmin(_ReadOnlyChangeLogAdmin):
    list_display = ("id", "family", "user", "action", "reason", "created_at")
    search_fields = ("family__name", "user__email", "reason")
    readonly_fields = ("family", "user", "action", "reason", "changes", "created_at")


@admin.register(SupplierChangeLog)
class SupplierChangeLogAdmin(_ReadOnlyChangeLogAdmin):
    list_display = ("id", "supplier", "user", "action", "reason", "created_at")
    search_fields = ("supplier__name", "user__email", "reason")
    readonly_fields = ("supplier", "user", "action", "reason", "changes", "created_at")


@admin.register(VatRate)
class VatRateAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "rate")
    search_fields = ("code", "label")
    readonly_fields = ("code", "label", "rate")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
