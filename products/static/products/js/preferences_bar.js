/* Centralized language + theme preferences bar (landing dashboards).

   Reads/writes the same localStorage keys the consoles use (cc-lang /
   cc-theme), so a choice made here is already applied when the user
   navigates to any console page.
*/
(function () {
    const LANG_KEY = "cc-lang";
    const THEME_KEY = "cc-theme";

    const DICT = {
        en: {
            language: "Language",
            themeDark: "Dark theme",
            themeLight: "Light theme",
            settings: "Settings",
            signedInAs: "Signed in as",
            signOut: "Sign out",
            help: "Help",
        },
        pt: {
            language: "Idioma",
            themeDark: "Tema escuro",
            themeLight: "Tema claro",
            settings: "Definições",
            signedInAs: "Sessão iniciada como",
            signOut: "Terminar sessão",
            help: "Ajuda",
        },
    };

    function safeGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function safeSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            /* ignore */
        }
    }

    function currentLang() {
        return safeGet(LANG_KEY, "en");
    }

    function currentTheme() {
        return safeGet(THEME_KEY, "light");
    }

    function t(key) {
        const dict = DICT[currentLang()] || DICT.en;
        return dict[key] || key;
    }

    function applyStaticI18n() {
        document.querySelectorAll("[data-i18n]").forEach((node) => {
            const key = node.getAttribute("data-i18n");
            if (DICT[currentLang()] && DICT[currentLang()][key]) {
                node.textContent = t(key);
            }
        });
        document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
            const key = node.getAttribute("data-i18n-aria");
            if (DICT[currentLang()] && DICT[currentLang()][key]) {
                node.setAttribute("aria-label", t(key));
            }
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const button = document.getElementById("pref-theme");
        if (button) {
            button.textContent = theme === "dark" ? t("themeLight") : t("themeDark");
            button.setAttribute("aria-label", theme === "dark" ? t("themeLight") : t("themeDark"));
        }
    }

    function bind() {
        const select = document.getElementById("pref-language");
        if (select) {
            select.value = currentLang();
            select.addEventListener("change", (event) => {
                safeSet(LANG_KEY, event.target.value);
                applyStaticI18n();
                applyTheme(currentTheme());
            });
        }
        const button = document.getElementById("pref-theme");
        if (button) {
            button.addEventListener("click", () => {
                const next = currentTheme() === "dark" ? "light" : "dark";
                safeSet(THEME_KEY, next);
                applyTheme(next);
            });
        }
        applyStaticI18n();
        applyTheme(currentTheme());
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
