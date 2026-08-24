from django.shortcuts import render

from .permissions import login_required_active


@login_required_active
def feed_page(request):
    return render(request, "company_voice/feed.html", {"user": request.user})
