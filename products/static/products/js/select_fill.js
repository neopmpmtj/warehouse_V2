"use strict";

/* Shared master-data <select> filler: placeholder / empty values first, then
   A–Z by the text the user sees (locale-aware, numeric-aware).

   Action pickers (choose a record before submit) use fillActionSelect so the
   empty sentinel is always "-----" and nothing is pre-selected.
   Filters keep fillSelect(..., "All…") — empty value means "no filter". */
(function (global) {
    var EMPTY_OPTION_LABEL = "-----";

    function selectLocale() {
        var raw = "pt";
        try {
            raw = global.localStorage.getItem("cc-lang") || "pt";
        } catch (error) {
            raw = "pt";
        }
        return String(raw).toLowerCase().indexOf("pt") === 0 ? "pt-PT" : "en";
    }

    function compareSelectLabels(left, right) {
        return String(left).localeCompare(String(right), selectLocale(), {
            sensitivity: "base",
            numeric: true,
        });
    }

    function optionSortValue(option) {
        if (option.sortValue != null && String(option.sortValue) !== "") {
            return String(option.sortValue);
        }
        return String(option.label == null ? "" : option.label);
    }

    function isPinned(option) {
        return option.value === "" || option.value == null;
    }

    function hasEmptyOption(select) {
        var i;
        for (i = 0; i < select.options.length; i += 1) {
            if (select.options[i].value === "") {
                return true;
            }
        }
        return false;
    }

    function fillSelect(select, options, placeholder, selected) {
        if (!select) {
            return;
        }
        var current = select.value;
        var target = selected !== undefined ? String(selected) : current;
        var pinned = [];
        var rest = [];
        (options || []).forEach(function (option) {
            if (isPinned(option)) {
                pinned.push(option);
            } else {
                rest.push(option);
            }
        });
        rest.sort(function (left, right) {
            return compareSelectLabels(optionSortValue(left), optionSortValue(right));
        });

        select.replaceChildren();
        if (placeholder) {
            var empty = document.createElement("option");
            empty.value = "";
            empty.textContent = placeholder;
            select.appendChild(empty);
        }
        pinned.concat(rest).forEach(function (option) {
            var node = document.createElement("option");
            node.value = option.value == null ? "" : option.value;
            node.textContent = option.label;
            if (option.disabled) {
                node.disabled = true;
            }
            select.appendChild(node);
        });
        var i;
        for (i = 0; i < select.options.length; i += 1) {
            if (select.options[i].value === target) {
                select.value = target;
                return;
            }
        }
        if (hasEmptyOption(select)) {
            select.value = "";
        }
    }

    function fillActionSelect(select, options, selected) {
        fillSelect(
            select,
            options,
            EMPTY_OPTION_LABEL,
            selected == null ? "" : String(selected)
        );
    }

    global.EMPTY_OPTION_LABEL = EMPTY_OPTION_LABEL;
    global.fillSelect = fillSelect;
    global.fillActionSelect = fillActionSelect;
    global.compareSelectLabels = compareSelectLabels;
})(window);
