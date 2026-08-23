(function () {
    function isShown(element) {
        return Boolean(element) && !element.hidden;
    }

    function dismissSettings() {
        const toggle = document.getElementById("settings-toggle");
        const popover = document.getElementById("settings-popover");
        if (!isShown(popover)) {
            return false;
        }
        if (toggle) {
            toggle.click();
            toggle.focus();
        } else {
            popover.hidden = true;
        }
        return true;
    }

    function topOverlay() {
        const dialogs = document.querySelectorAll(".dialog:not([hidden])");
        if (dialogs.length) {
            return dialogs[dialogs.length - 1];
        }
        const drawers = document.querySelectorAll(".drawer:not([hidden])");
        if (drawers.length) {
            return drawers[drawers.length - 1];
        }
        return null;
    }

    function dismissButton(overlay) {
        return (
            overlay.querySelector('.drawer-head [data-i18n="close"]') ||
            overlay.querySelector('[data-i18n="close"]') ||
            overlay.querySelector('[data-i18n="cancel"]')
        );
    }

    document.addEventListener(
        "keydown",
        (event) => {
            if (event.key !== "Escape" || event.defaultPrevented || event.isComposing) {
                return;
            }
            if (dismissSettings()) {
                event.preventDefault();
                event.stopPropagation();
                return;
            }
            const overlay = topOverlay();
            if (!overlay) {
                return;
            }
            const button = dismissButton(overlay);
            if (!button || button.disabled) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            button.click();
        },
        true
    );
})();
