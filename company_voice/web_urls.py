from django.urls import path

from . import views

urlpatterns = [
    path("company-voice/", views.feed_page, name="company_voice_feed"),
]
