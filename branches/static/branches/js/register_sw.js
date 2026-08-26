"use strict";

(function () {
    if (!("serviceWorker" in navigator)) {
        return;
    }
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/service-worker.js").catch(function (err) {
            if (typeof console !== "undefined" && console.warn) {
                console.warn("Service worker registration failed:", err);
            }
        });
    });
}());
