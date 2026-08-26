from django.contrib import admin
from django.urls import include, path

from branches.views import service_worker
from config.health import healthz
from config.views import user_manual_file

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("docs/user-manuals/<str:filename>", user_manual_file, name="user_manual_file"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("branch/", include("branches.web_urls")),
    path("branch/", include("orders.web_urls")),
    path("branch/", include("threads.web_urls")),
    path("api/", include("branches.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("threads.urls")),
    path("api/", include("products.urls")),
    path("api/", include("procurement.urls")),
    path("api/", include("inventory.urls")),
    path("", include("products.web_urls")),
    path("", include("procurement.web_urls")),
    path("", include("inventory.web_urls")),
    path("", include("orders.warehouse_web_urls")),
    path("", include("threads.warehouse_web_urls")),
    path("api/", include("company_voice.urls")),
    path("", include("company_voice.web_urls")),
]
