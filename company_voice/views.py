from django.shortcuts import render

from branches.services import home_url_for_request

from .permissions import login_required_active


@login_required_active
def feed_page(request):
    return render(
        request,
        "company_voice/feed.html",
        {"user": request.user, "home_url": home_url_for_request(request)},
    )
