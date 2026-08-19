from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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
)
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

    def test_operator_is_read_only(self):
        user = get_user_model().objects.create_user(
            email="operator@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(user, GROUP_OPERATORS)

        self.assertTrue(user.has_perm(VIEW_ITEM))
        self.assertTrue(can_view_catalog(user))
        self.assertFalse(user.has_perm(ADD_ITEM))
        self.assertFalse(user.has_perm(CHANGE_ITEM))
        self.assertFalse(user.has_perm(DELETE_ITEM))


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="login@example.com",
            password="test-pass-123",
        )
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
