from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import (
    ADD_ITEM,
    CHANGE_ITEM,
    DELETE_ITEM,
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    LEGACY_WAREHOUSE_GROUP_NAME,
    VIEW_ITEM,
    WAREHOUSE_GROUP_NAMES,
    assign_warehouse_group,
    set_warehouse_grade,
    sync_warehouse_groups,
)
from accounts.capabilities import can_approve_purchase_order, can_mutate_catalog
from products.permissions import can_view_catalog


class UserModelTests(TestCase):
    def test_create_user_uses_email_as_identifier(self):
        user = get_user_model().objects.create_user(
            email="user@example.com",
            password="test-pass-123",
        )

        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("test-pass-123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(can_view_catalog(user))

    def test_create_superuser_sets_staff_and_superuser_flags(self):
        user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="test-pass-123",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(can_view_catalog(user))


class WarehouseGroupTests(TestCase):
    def test_migrate_creates_three_warehouse_groups(self):
        names = set(Group.objects.values_list("name", flat=True))
        self.assertTrue(set(WAREHOUSE_GROUP_NAMES).issubset(names))
        self.assertFalse(
            Group.objects.filter(name=LEGACY_WAREHOUSE_GROUP_NAME).exists()
        )

    def test_admin_has_full_item_permissions(self):
        user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_ADMINS)

        self.assertTrue(user.has_perm(VIEW_ITEM))
        self.assertTrue(user.has_perm(ADD_ITEM))
        self.assertTrue(user.has_perm(CHANGE_ITEM))
        self.assertTrue(user.has_perm(DELETE_ITEM))
        self.assertFalse(user.is_staff)

    def test_manager_can_add_and_change_but_not_delete(self):
        user = get_user_model().objects.create_user(
            email="manager@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_MANAGERS)

        self.assertTrue(user.has_perm(VIEW_ITEM))
        self.assertTrue(user.has_perm(ADD_ITEM))
        self.assertTrue(user.has_perm(CHANGE_ITEM))
        self.assertFalse(user.has_perm(DELETE_ITEM))

    def test_operator_grade_one_cannot_mutate(self):
        user = get_user_model().objects.create_user(
            email="operator@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_OPERATORS)

        self.assertTrue(user.has_perm(VIEW_ITEM))
        self.assertTrue(can_view_catalog(user))
        self.assertTrue(user.has_perm(ADD_ITEM))
        self.assertTrue(user.has_perm(CHANGE_ITEM))
        self.assertFalse(user.has_perm(DELETE_ITEM))
        self.assertFalse(can_mutate_catalog(user))
        self.assertEqual(user.warehouse_grade, 1)

    def test_sync_warehouse_groups_is_idempotent(self):
        admins = Group.objects.get(name=GROUP_ADMINS)
        before = set(admins.permissions.values_list("codename", flat=True))

        sync_warehouse_groups()

        after = set(admins.permissions.values_list("codename", flat=True))
        self.assertEqual(before, after)
        self.assertTrue(after)

    def test_assign_warehouse_group_preserves_extra_permission(self):
        admins = Group.objects.get(name=GROUP_ADMINS)
        extra = Permission.objects.get(
            content_type__app_label="auth",
            codename="change_group",
        )
        admins.permissions.add(extra)

        user = get_user_model().objects.create_user(
            email="preserve@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_ADMINS)

        self.assertTrue(
            admins.permissions.filter(codename="change_group").exists()
        )

    def test_assign_warehouse_group_is_exclusive(self):
        user = get_user_model().objects.create_user(
            email="role-switch@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_MANAGERS)
        self.assertTrue(user.has_perm(ADD_ITEM))

        assign_warehouse_group(user, GROUP_OPERATORS)
        names = set(user.groups.values_list("name", flat=True))
        self.assertEqual(names & set(WAREHOUSE_GROUP_NAMES), {GROUP_OPERATORS})
        self.assertTrue(user.has_perm(ADD_ITEM))
        self.assertTrue(user.has_perm(VIEW_ITEM))
        self.assertFalse(can_mutate_catalog(user))
        self.assertEqual(user.warehouse_grade, 1)

    def test_assign_warehouse_group_resets_grade(self):
        user = get_user_model().objects.create_user(
            email="grade-reset@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_MANAGERS)
        set_warehouse_grade(user, 3)
        self.assertEqual(user.warehouse_grade, 3)
        self.assertTrue(can_approve_purchase_order(user))

        assign_warehouse_group(user, GROUP_MANAGERS)
        user.refresh_from_db()
        self.assertEqual(user.warehouse_grade, 1)
        self.assertFalse(can_approve_purchase_order(user))

    def test_operator_grade_two_can_mutate(self):
        user = get_user_model().objects.create_user(
            email="operator2@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_OPERATORS)
        set_warehouse_grade(user, 2)
        self.assertTrue(can_mutate_catalog(user))
        self.assertFalse(can_approve_purchase_order(user))

    def test_set_warehouse_grade_rejects_out_of_range(self):
        user = get_user_model().objects.create_user(
            email="grade-range@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_OPERATORS)
        with self.assertRaises(ValueError):
            set_warehouse_grade(user, 3)

    def test_sync_warehouse_groups_replaces_extra_permissions(self):
        admins = Group.objects.get(name=GROUP_ADMINS)
        extra = Permission.objects.get(
            content_type__app_label="auth",
            codename="change_group",
        )
        admins.permissions.add(extra)
        self.assertTrue(admins.permissions.filter(pk=extra.pk).exists())

        sync_warehouse_groups()

        self.assertFalse(admins.permissions.filter(pk=extra.pk).exists())


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="login@example.com",
            password="test-pass-123",
        )
        # Warehouse users land on the dashboard after login (lock 5).
        assign_warehouse_group(self.user, GROUP_ADMINS)
        self.client = Client()

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "test-pass-123"},
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_invalid_password_returns_form_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)


class DjangoAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.warehouse_admin = user_model.objects.create_user(
            email="warehouse.admin@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(self.warehouse_admin, GROUP_ADMINS)
        self.staff_user = user_model.objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client = Client()

    def test_superuser_can_open_admin(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_warehouse_admin_cannot_open_admin(self):
        self.client.force_login(self.warehouse_admin)

        response = self.client.get(reverse("admin:index"))

        self.assertIn(response.status_code, (302, 403))

    def test_staff_non_superuser_cannot_open_admin(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin:index"))

        self.assertIn(response.status_code, (302, 403))


class UserTimezoneTests(TestCase):
    def test_new_user_defaults_to_lisbon_timezone(self):
        from accounts.models import DEFAULT_USER_TIMEZONE

        user = get_user_model().objects.create_user(
            email="tz-default@example.com",
            password="test-pass-123",
        )

        self.assertEqual(user.timezone, DEFAULT_USER_TIMEZONE)
        self.assertEqual(DEFAULT_USER_TIMEZONE, "Europe/Lisbon")

    def test_middleware_activates_user_timezone(self):
        from datetime import datetime, timedelta

        from django.test import RequestFactory
        from django.utils import timezone

        from accounts.middleware import UserTimezoneMiddleware

        user = get_user_model().objects.create_user(
            email="tz-sg@example.com",
            password="test-pass-123",
        )
        user.timezone = "Asia/Singapore"
        user.save()

        request = RequestFactory().get("/")
        request.user = user

        observed = {}

        def get_response(req):
            observed["offset"] = timezone.get_current_timezone().utcoffset(
                datetime(2026, 1, 1)
            )

        UserTimezoneMiddleware(get_response)(request)

        self.assertEqual(observed["offset"], timedelta(hours=8))
        # After the request the timezone must be deactivated (no leak).
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        timezone.deactivate()

    def test_clean_rejects_unknown_timezone(self):
        from django.core.exceptions import ValidationError

        user = get_user_model().objects.create_user(
            email="tz-bad@example.com",
            password="test-pass-123",
        )
        user.timezone = "Not/AZone"

        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_clean_accepts_valid_timezone(self):
        user = get_user_model().objects.create_user(
            email="tz-ok@example.com",
            password="test-pass-123",
        )
        user.timezone = "Europe/Lisbon"
        user.full_clean()

    def test_middleware_deactivates_for_anonymous_user(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from django.utils import timezone

        from accounts.middleware import UserTimezoneMiddleware

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        UserTimezoneMiddleware(lambda r: None)(request)

        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        timezone.deactivate()


class InactiveSessionTests(TestCase):
    """Deactivated users must lose console/API access even with a live session."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="inactive-session@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(self.user, GROUP_ADMINS)
        self.client = Client()
        self.host = {"HTTP_HOST": "localhost"}

    def test_inactive_user_denied_api_and_session_cleared(self):
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(
            reverse("manage_item_list"),
            **self.host,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Account is inactive")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_denied_staff_page(self):
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.get(reverse("staff_dashboard"), **self.host)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_can_view_catalog_false_when_inactive(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(can_view_catalog(self.user))
