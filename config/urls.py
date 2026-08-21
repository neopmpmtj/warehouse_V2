from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("branch/", include("branches.urls")),
    path("api/", include("products.urls")),
    path("api/", include("procurement.urls")),
    path("api/", include("inventory.urls")),
    path("", include("products.web_urls")),
    path("", include("procurement.web_urls")),
    path("", include("inventory.web_urls")),
]
