{% load static %}

const CACHE_NAME = "centcompras-shell-v7";

const APP_SHELL = [
    "/",
    "{% static 'products/js/db.js' %}",
    "{% static 'products/js/product_list.js' %}",
    "{% static 'products/js/register_sw.js' %}"
];


self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(APP_SHELL))
    );

    self.skipWaiting();
});


self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        })
    );

    self.clients.claim();
});


self.addEventListener("fetch", (event) => {
    const requestUrl = new URL(event.request.url);

    // Network-only: APIs, staff console, auth, admin.
    if (
        requestUrl.pathname.startsWith("/api/")
        || requestUrl.pathname.startsWith("/manage/")
        || requestUrl.pathname.startsWith("/accounts/")
        || requestUrl.pathname.startsWith("/admin/")
        || requestUrl.pathname.startsWith("/branches/")
    ) {
        return;
    }

    // Cache-first only for the branch catalogue app shell.
    const isAppShell = APP_SHELL.some((entry) => {
        if (entry.startsWith("http")) {
            return event.request.url === entry;
        }
        return requestUrl.pathname === entry;
    });
    if (!isAppShell) {
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            return cachedResponse || fetch(event.request);
        })
    );
});