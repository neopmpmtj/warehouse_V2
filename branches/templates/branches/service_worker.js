{% load static %}
"use strict";

var CACHE_NAME = "centcompras-branch-v1";

var APP_SHELL = [
    "{% static 'products/css/settings_menu.css' %}?v=5",
    "{% static 'products/js/preferences_bar.js' %}?v=5",
    "{% static 'products/js/console_settings_menu.js' %}?v=1",
    "{% static 'branches/js/db.js' %}?v=1",
    "{% static 'branches/js/register_sw.js' %}?v=1",
    "{% static 'branches/js/branch_catalog.js' %}?v=1",
    "{% static 'branches/js/sync_queue.js' %}?v=1",
    "{% static 'branches/js/branch_offline.js' %}?v=1",
    "{% static 'orders/js/branch_requests.js' %}?v=1",
    "{% static 'branches/manifest.webmanifest' %}",
    "{% static 'branches/icons/icon.svg' %}",
];

var BRANCH_PATH_PREFIX = "/branch/";

function isBypassed(url) {
    return (
        url.pathname.indexOf("/api/") !== -1 ||
        url.pathname.indexOf("/accounts/") !== -1 ||
        url.pathname.indexOf("/admin/") !== -1
    );
}

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(APP_SHELL);
        })
    );
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(
                names
                    .filter(function (name) {
                        return name !== CACHE_NAME;
                    })
                    .map(function (name) {
                        return caches.delete(name);
                    })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener("fetch", function (event) {
    if (event.request.method !== "GET") {
        return;
    }

    var url = new URL(event.request.url);
    if (isBypassed(url)) {
        return;
    }

    if (url.pathname.indexOf(BRANCH_PATH_PREFIX) === 0 || APP_SHELL.indexOf(url.pathname) !== -1) {
        event.respondWith(
            caches.match(event.request).then(function (cached) {
                var networkFetch = fetch(event.request)
                    .then(function (response) {
                        if (response && response.ok) {
                            var copy = response.clone();
                            caches.open(CACHE_NAME).then(function (cache) {
                                cache.put(event.request, copy);
                            });
                        }
                        return response;
                    })
                    .catch(function () {
                        return cached;
                    });
                return cached || networkFetch;
            })
        );
        return;
    }

    if (url.pathname.indexOf("/static/") !== -1) {
        event.respondWith(
            caches.match(event.request).then(function (cached) {
                return (
                    cached ||
                    fetch(event.request).then(function (response) {
                        if (response && response.ok) {
                            var copy = response.clone();
                            caches.open(CACHE_NAME).then(function (cache) {
                                cache.put(event.request, copy);
                            });
                        }
                        return response;
                    })
                );
            })
        );
    }
});
