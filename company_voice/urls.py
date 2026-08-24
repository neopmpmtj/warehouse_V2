from django.urls import path

from . import console_views

urlpatterns = [
    path("company-voice/feed/", console_views.feed_api, name="company_voice_feed_api"),
    path("company-voice/posts/", console_views.post_create, name="company_voice_post_create"),
    path(
        "company-voice/posts/<int:post_id>/",
        console_views.post_update,
        name="company_voice_post_update",
    ),
    path(
        "company-voice/posts/<int:post_id>/delete/",
        console_views.post_delete,
        name="company_voice_post_delete",
    ),
    path(
        "company-voice/posts/<int:post_id>/comments/",
        console_views.comment_create,
        name="company_voice_comment_create",
    ),
    path(
        "company-voice/comments/<int:comment_id>/",
        console_views.comment_update,
        name="company_voice_comment_update",
    ),
    path(
        "company-voice/comments/<int:comment_id>/delete/",
        console_views.comment_delete,
        name="company_voice_comment_delete",
    ),
]
