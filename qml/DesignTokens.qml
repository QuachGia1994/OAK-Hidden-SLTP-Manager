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

    // ── Hex→QML-color helper ──
    function colorFromHex(value) {
        var hex = String(value || "#000000").replace("#", "");
        return Qt.rgba(
            parseInt(hex.slice(0, 2), 16) / 255,
            parseInt(hex.slice(2, 4), 16) / 255,
            parseInt(hex.slice(4, 6), 16) / 255,
            1
        );
    }

    // ── Complete palette lookup ──
    function palette(themeName) {
        var t = themeName || Theme.currentTheme;
        var palettes = {
            "dark": {
                windowBg: colorFromHex("#0b0f14"), surface: colorFromHex("#111820"), border: colorFromHex("#1e2937"),
                text: colorFromHex("#e6edf3"), muted: colorFromHex("#8b98a5"), accent: colorFromHex("#2fa572"),
                divider: colorFromHex("#1e2937"), navActiveBg: colorFromHex("#111820"), navActiveLeft: colorFromHex("#2fa572"),
                inputBg: colorFromHex("#1c2836")
            },
            "light": {
                windowBg: colorFromHex("#eef1f5"), surface: colorFromHex("#ffffff"), border: colorFromHex("#c3ccd6"),
                text: colorFromHex("#141b24"), muted: colorFromHex("#4b5a6b"), accent: colorFromHex("#147a52"),
                divider: colorFromHex("#c3ccd6"), navActiveBg: colorFromHex("#eef1f5"), navActiveLeft: colorFromHex("#147a52"),
                inputBg: colorFromHex("#f7f9fc")
            },
            "deep-sea": {
                windowBg: colorFromHex("#031016"), surface: colorFromHex("#061219"), border: colorFromHex("#1b3b45"),
                text: colorFromHex("#e8fbff"), muted: colorFromHex("#8caab2"), accent: colorFromHex("#18d6ff"),
                divider: colorFromHex("#1b3b45"), navActiveBg: colorFromHex("#09232c"), navActiveLeft: colorFromHex("#18d6ff"),
                inputBg: colorFromHex("#0e2530")
            },
            "contrast": {
                windowBg: colorFromHex("#000000"), surface: colorFromHex("#0d0d0d"), border: colorFromHex("#4d4d4d"),
                text: colorFromHex("#ffffff"), muted: colorFromHex("#b3b3b3"), accent: colorFromHex("#00e676"),
                divider: colorFromHex("#4d4d4d"), navActiveBg: colorFromHex("#0d0d0d"), navActiveLeft: colorFromHex("#00e676"),
                inputBg: colorFromHex("#1a1a1a")
            }
        };
        return palettes[t] || palettes["dark"];
    }
}
