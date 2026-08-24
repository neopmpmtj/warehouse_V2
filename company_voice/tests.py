from datetime import timedelta
import json
import threading

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import assign_warehouse_group, GROUP_ADMINS
from branches.models import BranchMembership
from branches.services import assign_membership, create_branch

from .admin import VoicePostAdmin
from .models import VoiceChangeLog, VoiceComment, VoicePost, VoiceSubThread
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
    InvalidAnonymousError,
    NotAuthorError,
    StaleEditError,
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
        self.assertIsNone(post.edited_at)
        self.assertTrue(
            VoiceChangeLog.objects.filter(
                post=post,
                action=VoiceChangeLog.Action.POST_CREATED,
            ).exists()
        )

    def test_edit_within_window(self):
        post = create_post(self.warehouse_user, "Original")
        post = edit_post(
            self.warehouse_user,
            post,
            "Updated",
            tag="wish",
            expected_updated_at=post.updated_at,
        )
        post.refresh_from_db()
        self.assertEqual(post.body, "Updated")
        self.assertEqual(post.tag, "wish")
        self.assertIsNotNone(post.edited_at)

    def test_edit_after_window_raises(self):
        post = create_post(self.warehouse_user, "Original")
        post.created_at = timezone.now() - EDIT_WINDOW - timedelta(seconds=1)
        post.save(update_fields=["created_at"])
        with self.assertRaises(EditWindowExpiredError):
            edit_post(
                self.warehouse_user,
                post,
                "Too late",
                expected_updated_at=post.updated_at,
            )

    def test_non_author_cannot_edit(self):
        post = create_post(self.warehouse_user, "Mine")
        with self.assertRaises(NotAuthorError):
            edit_post(
                self.branch_user,
                post,
                "Theirs",
                expected_updated_at=post.updated_at,
            )

    def test_stale_edit_rejected(self):
        post = create_post(self.warehouse_user, "Original")
        edit_post(
            self.warehouse_user,
            post,
            "First",
            expected_updated_at=post.updated_at,
        )
        with self.assertRaises(StaleEditError):
            edit_post(
                self.warehouse_user,
                post,
                "Second",
                expected_updated_at=post.updated_at,
            )

    def test_null_tag_clears(self):
        post = create_post(self.warehouse_user, "Tagged", tag="wish")
        post = edit_post(
            self.warehouse_user,
            post,
            "Tagged",
            tag=None,
            expected_updated_at=post.updated_at,
        )
        post.refresh_from_db()
        self.assertEqual(post.tag, "")

    def test_anonymous_rejects_string_false(self):
        with self.assertRaises(InvalidAnonymousError):
            create_post(self.warehouse_user, "Hi", is_anonymous="false")

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
        self.assertTrue(
            VoiceChangeLog.objects.filter(
                post=post,
                action=VoiceChangeLog.Action.POST_DELETED,
            ).exists()
        )


class CommentServiceTests(CompanyVoiceTestMixin, TestCase):
    def test_anyone_can_comment_and_creates_sub_thread(self):
        post = create_post(self.warehouse_user, "Topic")
        comment = add_comment(self.branch_user, post, "I agree")
        self.assertTrue(VoiceSubThread.objects.filter(post=post).exists())
        self.assertEqual(comment.author_id, self.branch_user.pk)
        self.assertIsNone(comment.edited_at)

    def test_delete_comment_only_affects_comment(self):
        post = create_post(self.warehouse_user, "Topic")
        comment = add_comment(self.branch_user, post, "Remove me")
        delete_comment(self.branch_user, comment)
        comment.refresh_from_db()
        post.refresh_from_db()
        self.assertIsNotNone(comment.deleted_at)
        self.assertIsNone(post.deleted_at)

    def test_edit_comment_sets_edited_at(self):
        post = create_post(self.warehouse_user, "Topic")
        comment = add_comment(self.branch_user, post, "Draft")
        comment = edit_comment(
            self.branch_user,
            comment,
            "Final",
            expected_updated_at=comment.updated_at,
        )
        comment.refresh_from_db()
        self.assertEqual(comment.body, "Final")
        self.assertIsNotNone(comment.edited_at)


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
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="lang-select"')
        self.assertContains(response, "settings-icon")
        self.assertContains(response, 'id="settings-help"')
        self.assertNotContains(response, 'id="theme-toggle"')

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
        self.assertFalse(payload["post"]["edited"])
        self.assertIn("updated_at", payload["post"])

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.post(
            reverse("company_voice_post_create"),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_json_array_returns_400(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.post(
            reverse("company_voice_post_create"),
            data="[]",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_json")

    def test_anonymous_string_false_rejected(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.post(
            reverse("company_voice_post_create"),
            data='{"body": "Hello", "is_anonymous": "false"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_anonymous")

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
        self.assertFalse(data["posts"][0]["edited"])

    def test_comment_count_excludes_deleted(self):
        post = create_post(self.warehouse_user, "Discuss")
        keep = add_comment(self.branch_user, post, "Keep")
        gone = add_comment(self.warehouse_user, post, "Gone")
        delete_comment(self.warehouse_user, gone)
        self.client.force_login(self.branch_user)
        response = self.client.get(reverse("company_voice_feed_api"))
        sub = response.json()["posts"][0]["sub_thread"]
        self.assertEqual(sub["comment_count"], 1)
        self.assertEqual(len(sub["comments"]), 2)
        self.assertEqual(keep.body, "Keep")

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
        self.assertFalse(response.json()["comment"]["edited"])

    def test_edit_post_via_api(self):
        post = create_post(self.warehouse_user, "Before")
        self.client.force_login(self.warehouse_user)
        response = self.client.patch(
            reverse("company_voice_post_update", args=[post.pk]),
            data=json.dumps({
                "body": "After",
                "tag": "wish",
                "updated_at": post.updated_at.isoformat(),
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["post"]
        self.assertEqual(payload["body"], "After")
        self.assertEqual(payload["tag"], "wish")
        self.assertTrue(payload["edited"])

    def test_stale_edit_via_api_returns_409(self):
        post = create_post(self.warehouse_user, "Before")
        first_updated = post.updated_at.isoformat()
        self.client.force_login(self.warehouse_user)
        self.client.patch(
            reverse("company_voice_post_update", args=[post.pk]),
            data=json.dumps({"body": "Mid", "updated_at": first_updated}),
            content_type="application/json",
        )
        response = self.client.patch(
            reverse("company_voice_post_update", args=[post.pk]),
            data=json.dumps({"body": "Late", "updated_at": first_updated}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "stale_edit")

    def test_tag_null_clears_via_api(self):
        post = create_post(self.warehouse_user, "Tagged", tag="praise")
        self.client.force_login(self.warehouse_user)
        response = self.client.patch(
            reverse("company_voice_post_update", args=[post.pk]),
            data=json.dumps({
                "body": "Tagged",
                "tag": None,
                "updated_at": post.updated_at.isoformat(),
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["post"]["tag"])

    def test_non_author_cannot_delete(self):
        post = create_post(self.warehouse_user, "Mine")
        self.client.force_login(self.branch_user)
        response = self.client.delete(
            reverse("company_voice_post_delete", args=[post.pk]),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "not_author")


class VoiceAdminTests(CompanyVoiceTestMixin, TestCase):
    def test_hard_delete_disabled_for_superuser(self):
        superuser = User.objects.create_superuser(
            email="voice.super@centcompras.dev",
            password="pass",
        )
        request = RequestFactory().get("/admin/")
        request.user = superuser
        model_admin = VoicePostAdmin(VoicePost, AdminSite())
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))


class ConcurrentVoiceTests(TransactionTestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="voice.author@centcompras.dev",
            password="pass",
        )
        self.commenter = User.objects.create_user(
            email="voice.commenter@centcompras.dev",
            password="pass",
        )
        self.other = User.objects.create_user(
            email="voice.other@centcompras.dev",
            password="pass",
        )

    def test_comment_vs_delete_does_not_leave_live_sub_thread(self):
        post = create_post(self.author, "Race parent")
        outcomes = []

        def do_comment():
            try:
                add_comment(self.commenter, post, "Late reply")
                outcomes.append("commented")
            except ValidationError as exc:
                outcomes.append(getattr(exc, "code", None) or "error")
            finally:
                connection.close()

        def do_delete():
            try:
                delete_post(self.author, post)
                outcomes.append("deleted")
            except ValidationError as exc:
                outcomes.append(getattr(exc, "code", None) or "error")
            finally:
                connection.close()

        workers = [
            threading.Thread(target=do_comment),
            threading.Thread(target=do_delete),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        post.refresh_from_db()
        self.assertIsNotNone(post.deleted_at)
        self.assertFalse(
            VoiceComment.objects.filter(
                sub_thread__post=post,
                deleted_at__isnull=True,
            ).exists()
        )

    def test_two_first_comments_share_one_sub_thread(self):
        post = create_post(self.author, "Open discussion")
        outcomes = []

        def worker(user, body):
            try:
                add_comment(user, post, body)
                outcomes.append("ok")
            except Exception:
                outcomes.append("error")
            finally:
                connection.close()

        threads = [
            threading.Thread(target=worker, args=(self.commenter, "One")),
            threading.Thread(target=worker, args=(self.other, "Two")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes.count("ok"), 2)
        self.assertEqual(VoiceSubThread.objects.filter(post=post).count(), 1)
        self.assertEqual(VoiceComment.objects.filter(sub_thread__post=post).count(), 2)
