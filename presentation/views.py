from django.shortcuts import render

SLIDE_COUNT = 16


def deck_pt(request):
    """Browser slide deck for CentCompras (pt-PT). Public — no live data."""
    return render(
        request,
        "presentation/deck_pt.html",
        {
            "slide_count": SLIDE_COUNT,
            "lang": "pt-PT",
            "lang_label": "Português",
            "other_lang_url": "/presentation/en/",
            "other_lang_label": "English",
        },
    )


def deck_en(request):
    """Browser slide deck for CentCompras (en). Public — no live data."""
    return render(
        request,
        "presentation/deck_en.html",
        {
            "slide_count": SLIDE_COUNT,
            "lang": "en",
            "lang_label": "English",
            "other_lang_url": "/presentation/pt/",
            "other_lang_label": "Português",
        },
    )
