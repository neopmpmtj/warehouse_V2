from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import assign_warehouse_group, GROUP_ADMINS
from branches.models import Branch, BranchMembership
from branches.services import assign_membership, create_branch

from .models import VoiceComment, VoicePost, VoiceSubThread
from .services import (
    EDIT_WINDOW,
    add_comment,
    create_post,
    delete_comment,
    delete_post,
    display_name,
    edit_comment,
    edit_post,
    EditWindowExpiredError,
    NotAuthorError,
)

User = get_user_model()


class CompanyVoiceTestMixin:
    def setUp(self):
        self.warehouse_user = User.objects.create_user(
            email="warehouse.voice@centcompras.dev",
            password="pass",
            first_name="Warehouse",
        )
        assign_warehouse_group(self.warehouse_user, GROUP_ADMINS)

        self.branch_user = User.objects.create_user(
            email="branch.voice@centcompras.dev",
            password="pass",
            first_name="Branch",
        )
        branch = create_branch("Voice Test Branch")
        assign_membership(self.branch_user, branch, BranchMembership.Role.OPERATOR)

        self.other_user = User.objects.create_user(
            email="other.voice@centcompras.dev",
            password="pass",
        )


class DisplayNameTests(CompanyVoiceTestMixin, TestCase):
    def test_named_uses_first_name(self):
        self.assertEqual(
            display_name(self.warehouse_user, False),
            "Warehouse",
        )

    def test_named_falls_back_to_email_local_part(self):
        user = User.objects.create_user(email="alpha.beta@centcompras.dev", password="pass")
        self.assertEqual(display_name(user, False), "alpha.beta")

    def test_anonymous(self):
        self.assertEqual(display_name(self.warehouse_user, True), "Anonymous")


class PostServiceTests(CompanyVoiceTestMixin, TestCase):
    def test_create_post_with_tag_and_anonymous(self):
        post = create_post(
            self.warehouse_user,
            "Great teamwork!",
            tag="praise",
            is_anonymous=True,
        )
        self.assertEqual(post.body, "Great teamwork!")
        self.assertEqual(post.tag, "praise")
        self.assertTrue(post.is_anonymous)

    def test_edit_within_window(self):
        post = create_post(self.warehouse_user, "Original")
        post = edit_post(self.warehouse_user, post, "Updated", tag="wish")
        post.refresh_from_db()
        self.assertEqual(post.body, "Updated")
        self.assertEqual(post.tag, "wish")

    def test_edit_after_window_raises(self):
        post = create_post(self.warehouse_user, "Original")
        post.created_at = timezone.now() - EDIT_WINDOW - timedelta(seconds=1)
        post.save(update_fields=["created_at"])
        with self.assertRaises(EditWindowExpiredError):
            edit_post(self.warehouse_user, post, "Too late")

    def test_non_author_cannot_edit(self):
        post = create_post(self.warehouse_user, "Mine")
        with self.assertRaises(NotAuthorError):
            edit_post(self.branch_user, post, "Theirs")

    def test_delete_post_cascades_sub_thread_and_comments(self):
        post = create_post(self.warehouse_user, "Parent")
        add_comment(self.branch_user, post, "Reply one")
        add_comment(self.warehouse_user, post, "Reply two")
        delete_post(self.warehouse_user, post)
        post.refresh_from_db()
        sub = post.sub_thread
        sub.refresh_from_db()
        comments = VoiceComment.objects.filter(sub_thread=sub)
        self.assertIsNotNone(post.deleted_at)
        self.assertIsNotNone(sub.deleted_at)
        self.assertTrue(all(c.deleted_at is not None for c in comments))


class CommentServiceTests(CompanyVoiceTestMixin, TestCase):
    def test_anyone_can_comment_and_creates_sub_thread(self):
        post = create_post(self.warehouse_user, "Topic")
        comment = add_comment(self.branch_user, post, "I agree")
        self.assertTrue(VoiceSubThread.objects.filter(post=post).exists())
        self.assertEqual(comment.author_id, self.branch_user.pk)

    def test_delete_comment_only_affects_comment(self):
        post = create_post(self.warehouse_user, "Topic")
        comment = add_comment(self.branch_user, post, "Remove me")
        delete_comment(self.branch_user, comment)
        comment.refresh_from_db()
        post.refresh_from_db()
        self.assertIsNotNone(comment.deleted_at)
        self.assertIsNone(post.deleted_at)


class FeedApiTests(CompanyVoiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_anonymous_redirected_from_page(self):
        response = self.client.get(reverse("company_voice_feed"))
        self.assertEqual(response.status_code, 302)

    def test_warehouse_user_can_load_feed_page(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.get(reverse("company_voice_feed"))
        self.assertEqual(response.status_code, 200)

    def test_branch_user_can_load_feed_page(self):
        self.client.force_login(self.branch_user)
        response = self.client.get(reverse("company_voice_feed"))
        self.assertEqual(response.status_code, 200)

    def test_create_post_via_api(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.post(
            reverse("company_voice_post_create"),
            data='{"body": "Hello company", "tag": "suggestion", "is_anonymous": true}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["post"]["display_name"], "Anonymous")
        self.assertTrue(payload["post"]["is_anonymous"])

    def test_feed_shows_deleted_placeholder(self):
        post = create_post(self.warehouse_user, "Gone")
        delete_post(self.warehouse_user, post)
        self.client.force_login(self.branch_user)
        response = self.client.get(reverse("company_voice_feed_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["posts"]), 1)
        self.assertTrue(data["posts"][0]["deleted"])
        self.assertIsNone(data["posts"][0]["body"])
        self.assertEqual(data["posts"][0]["display_name"], "[Deleted by author]")

    def test_comment_api(self):
        post = create_post(self.warehouse_user, "Discuss")
        self.client.force_login(self.branch_user)
        response = self.client.post(
            reverse("company_voice_comment_create", args=[post.pk]),
            data='{"body": "My take", "is_anonymous": false}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["comment"]["display_name"], "Branch")

    def test_edit_post_via_api(self):
        post = create_post(self.warehouse_user, "Before")
        self.client.force_login(self.warehouse_user)
        response = self.client.patch(
            reverse("company_voice_post_update", args=[post.pk]),
            data='{"body": "After", "tag": "wish"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["post"]["body"], "After")
        self.assertEqual(response.json()["post"]["tag"], "wish")

    def test_non_author_cannot_delete(self):
        post = create_post(self.warehouse_user, "Mine")
        self.client.force_login(self.branch_user)
        response = self.client.delete(
            reverse("company_voice_post_delete", args=[post.pk]),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "not_author")
