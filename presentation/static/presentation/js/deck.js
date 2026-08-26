(function () {
    "use strict";

    var slides = document.querySelectorAll(".slide");
    var total = slides.length;
    var current = 0;
    var progress = document.getElementById("deck-progress");
    var counter = document.getElementById("slide-counter");
    var btnPrev = document.getElementById("btn-prev");
    var btnNext = document.getElementById("btn-next");
    var helpOverlay = document.getElementById("help-overlay");
    var btnHelp = document.getElementById("btn-help");
    var btnHelpClose = document.getElementById("btn-help-close");

    function showSlide(index) {
        if (index < 0 || index >= total) {
            return;
        }
        slides.forEach(function (slide, i) {
            slide.classList.remove("active", "prev");
            if (i === index) {
                slide.classList.add("active");
            } else if (i < index) {
                slide.classList.add("prev");
            }
        });
        current = index;
        if (progress) {
            progress.style.width = ((current + 1) / total * 100) + "%";
        }
        if (counter) {
            counter.textContent = (current + 1) + " / " + total;
        }
        if (btnPrev) {
            btnPrev.disabled = current === 0;
        }
        if (btnNext) {
            btnNext.disabled = current === total - 1;
        }
        if (window.location.hash !== "#" + (current + 1)) {
            history.replaceState(null, "", "#" + (current + 1));
        }
    }

    function next() {
        showSlide(Math.min(current + 1, total - 1));
    }

    function prev() {
        showSlide(Math.max(current - 1, 0));
    }

    function toggleHelp() {
        if (helpOverlay) {
            helpOverlay.classList.toggle("visible");
        }
    }

    function toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(function () {});
            document.body.classList.add("deck-fullscreen");
        } else {
            document.exitFullscreen();
            document.body.classList.remove("deck-fullscreen");
        }
    }

    function initFromHash() {
        var hash = window.location.hash.replace("#", "");
        var num = parseInt(hash, 10);
        if (!isNaN(num) && num >= 1 && num <= total) {
            showSlide(num - 1);
        } else {
            showSlide(0);
        }
    }

    if (btnPrev) {
        btnPrev.addEventListener("click", prev);
    }
    if (btnNext) {
        btnNext.addEventListener("click", next);
    }
    if (btnHelp) {
        btnHelp.addEventListener("click", toggleHelp);
    }
    if (btnHelpClose) {
        btnHelpClose.addEventListener("click", toggleHelp);
    }

    document.addEventListener("keydown", function (e) {
        if (helpOverlay && helpOverlay.classList.contains("visible")) {
            if (e.key === "Escape" || e.key === "?") {
                toggleHelp();
            }
            return;
        }
        switch (e.key) {
            case "ArrowRight":
            case "ArrowDown":
            case " ":
            case "PageDown":
                e.preventDefault();
                next();
                break;
            case "ArrowLeft":
            case "ArrowUp":
            case "PageUp":
                e.preventDefault();
                prev();
                break;
            case "Home":
                e.preventDefault();
                showSlide(0);
                break;
            case "End":
                e.preventDefault();
                showSlide(total - 1);
                break;
            case "f":
            case "F":
                e.preventDefault();
                toggleFullscreen();
                break;
            case "?":
                e.preventDefault();
                toggleHelp();
                break;
            case "Escape":
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                    document.body.classList.remove("deck-fullscreen");
                }
                break;
        }
    });

    window.addEventListener("hashchange", initFromHash);

    document.addEventListener("fullscreenchange", function () {
        if (!document.fullscreenElement) {
            document.body.classList.remove("deck-fullscreen");
        }
    });

    /* Touch swipe */
    var touchStartX = 0;
    var deck = document.querySelector(".deck-slides");
    if (deck) {
        deck.addEventListener("touchstart", function (e) {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });
        deck.addEventListener("touchend", function (e) {
            var diff = e.changedTouches[0].screenX - touchStartX;
            if (Math.abs(diff) > 50) {
                if (diff < 0) {
                    next();
                } else {
                    prev();
                }
            }
        }, { passive: true });
    }

    initFromHash();
})();
