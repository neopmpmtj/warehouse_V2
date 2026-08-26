"use strict";

(function () {
    var DB_NAME = "centcompras_branch";
    var submitting = false;

    function wipeThenSubmit(form) {
        var done = false;
        function finish() {
            if (done) {
                return;
            }
            done = true;
            submitting = true;
            form.submit();
        }
        try {
            var request = indexedDB.deleteDatabase(DB_NAME);
            request.onsuccess = finish;
            request.onerror = finish;
            request.onblocked = finish;
        } catch (err) {
            finish();
        }
        setTimeout(finish, 1500);
    }

    document.addEventListener(
        "submit",
        function (event) {
            var form = event.target;
            if (!form || !form.classList || !form.classList.contains("settings-signout-form")) {
                return;
            }
            if (submitting) {
                return;
            }
            event.preventDefault();
            wipeThenSubmit(form);
        },
        true
    );
}());
