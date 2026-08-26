"""Tests for project-level views (user-manual serving)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserManualFileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="manual.reader@centcompras.dev",
            password="devpass123",
        )

    def test_anonymous_manual_redirects_to_login(self):
        url = reverse("user_manual_file", args=["pt", "01-items.pdf"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_pt_pdf_served_when_logged_in(self):
        self.client.force_login(self.user)
        url = reverse("user_manual_file", args=["pt", "01-items.pdf"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_pt_md_served_when_logged_in(self):
        self.client.force_login(self.user)
        url = reverse("user_manual_file", args=["pt", "05-edge-cases-and-limits.md"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response["Content-Type"])

    def test_unknown_lang_404(self):
        self.client.force_login(self.user)
        url = reverse("user_manual_file", args=["fr", "01-items.pdf"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_rejected(self):
        self.client.force_login(self.user)
        response = self.client.get("/docs/user-manuals/pt/../en/01-items.pdf")
        self.assertEqual(response.status_code, 404)
