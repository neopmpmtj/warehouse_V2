from django.shortcuts import render


def deck(request):
    """Browser slide deck for CentCompras (pt-PT). Public — no live data."""
    return render(
        request,
        "presentation/deck.html",
        {
            "slide_count": 16,
            "lang": "pt-PT",
        },
    )
