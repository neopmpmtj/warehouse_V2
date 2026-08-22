(function () {
    function bindSettingsMenu() {
        const toggle = document.getElementById("settings-toggle");
        const popover = document.getElementById("settings-popover");
        if (!toggle || !popover) {
            return;
        }

        function setOpen(open) {
            popover.hidden = !open;
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }

        toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            setOpen(popover.hidden);
        });
        document.addEventListener("click", (event) => {
            if (popover.hidden) {
                return;
            }
            if (popover.contains(event.target) || toggle.contains(event.target)) {
                return;
            }
            setOpen(false);
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !popover.hidden) {
                setOpen(false);
                toggle.focus();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindSettingsMenu);
    } else {
        bindSettingsMenu();
    }
})();
