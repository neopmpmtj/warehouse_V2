"use strict";

(function () {
    if (typeof BranchOffline !== "undefined") {
        BranchOffline.bindOfflineBanner("offline-banner");
    }
    if (typeof BranchSyncQueue !== "undefined") {
        BranchSyncQueue.bindAutoSync(function () {
            window.dispatchEvent(new CustomEvent("branch-sync-complete"));
        });
    }
}());
