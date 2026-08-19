from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


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

    def test_create_superuser_sets_staff_and_superuser_flags(self):
        user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="test-pass-123",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="login@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client = Client()

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "test-pass-123"},
        )

        self.assertRedirects(response, "/")
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_invalid_password_returns_form_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse("_auth_user_id" in self.client.session)
