// -*- coding: utf-8 -*-
pragma Singleton
import QtQuick 2.15

QtObject {
    id: tokens

    // ── Shared metrics ──
    readonly property int spacing: 4
    readonly property int railWidth: 330
    readonly property int radius: 14
    readonly property int fontNav: 14
    readonly property int fontTiny: 12
    readonly property int fontBody: 13

    // ── Reactive current theme ──
    readonly property string currentTheme: Theme.currentTheme

    // ── Complete palette lookup ──
    function palette(themeName) {
        var t = themeName || Theme.currentTheme;
        var palettes = {
            "dark": {
                windowBg: "#0b0f14", surface: "#111820", border: "#1e2937",
                text: "#e6edf3", muted: "#8b98a5", accent: "#2fa572",
                divider: "#1e2937", navActiveBg: "#111820", navActiveLeft: "#2fa572"
            },
            "light": {
                windowBg: "#eef1f5", surface: "#ffffff", border: "#c3ccd6",
                text: "#141b24", muted: "#4b5a6b", accent: "#147a52",
                divider: "#c3ccd6", navActiveBg: "#eef1f5", navActiveLeft: "#147a52"
            },
            "deep-sea": {
                windowBg: "#031016", surface: "#061219", border: "#1b3b45",
                text: "#e8fbff", muted: "#8caab2", accent: "#18d6ff",
                divider: "#1b3b45", navActiveBg: "#09232c", navActiveLeft: "#18d6ff"
            },
            "contrast": {
                windowBg: "#000000", surface: "#0d0d0d", border: "#4d4d4d",
                text: "#ffffff", muted: "#b3b3b3", accent: "#00e676",
                divider: "#4d4d4d", navActiveBg: "#0d0d0d", navActiveLeft: "#00e676"
            }
        };
        return palettes[t] || palettes["dark"];
    }
}
