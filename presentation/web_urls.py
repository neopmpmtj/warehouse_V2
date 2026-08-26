from django.urls import path

from . import views

urlpatterns = [
    path("", views.deck_pt, name="presentation_deck_pt"),
    path("pt/", views.deck_pt, name="presentation_deck_pt_explicit"),
    path("en/", views.deck_en, name="presentation_deck_en"),
]
