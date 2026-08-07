// -*- coding: utf-8 -*-
pragma Singleton
import QtQuick 2.15

QtObject {
    id: themeRoot

    property string currentTheme: "dark"
    property string lang: "VN"

    function setTheme(name) {
        var normalized = String(name || "dark").toLowerCase().replace("_", "-").trim();
        var valid = ["dark", "light", "deep-sea", "contrast"];
        if (valid.indexOf(normalized) >= 0) {
            currentTheme = normalized;
        }
    }

    function toggleTheme() {
        var themes = ["dark", "light", "deep-sea", "contrast"];
        var idx = themes.indexOf(currentTheme);
        idx = (idx + 1) % themes.length;
        currentTheme = themes[idx];
    }

    function setLang(l) {
        var upper = String(l || "EN").toUpperCase();
        if (upper === "VN" || upper === "EN") {
            lang = upper;
        }
    }
}
