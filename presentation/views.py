from django.shortcuts import render

SLIDE_COUNT = 17
DEMO_LOGIN_URL = "http://169.58.240.120/accounts/login/"
DEMO_PASSWORD = "devpass123"


def _deck_context(extra):
    return {
        "slide_count": SLIDE_COUNT,
        "demo_login_url": DEMO_LOGIN_URL,
        "demo_password": DEMO_PASSWORD,
        **extra,
    }


def deck_pt(request):
    """Browser slide deck for CentCompras (pt-PT). Public — no live data."""
    return render(
        request,
        "presentation/deck_pt.html",
        _deck_context(
            {
                "lang": "pt-PT",
                "lang_label": "Português",
                "other_lang_url": "/presentation/en/",
                "other_lang_label": "English",
            }
        ),
    )


def deck_en(request):
    """Browser slide deck for CentCompras (en). Public — no live data."""
    return render(
        request,
        "presentation/deck_en.html",
        _deck_context(
            {
                "lang": "en",
                "lang_label": "English",
                "other_lang_url": "/presentation/pt/",
                "other_lang_label": "Português",
            }
        ),
    )
