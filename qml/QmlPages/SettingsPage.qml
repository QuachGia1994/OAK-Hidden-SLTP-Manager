// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Settings"
    color: "transparent"
    anchors.fill: parent

    // ── Palette ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    // ── Error tone (theme-neutral) ──
    readonly property color danger: "#e5534b"

    // ── i18n helper ──
    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    // ── Data + logic (TEST HOOKS) ──
    property var settings: ({})
    property bool saving: false
    property string errorText: ""
    property string savedMsg: ""

    // ── Derived ──
    property string langValue: (settings && settings.lang) || "VN"
    property string themeValue: normalizeTheme((settings && settings.theme))
    property bool ghostActive: !!(settings && settings.ghost_mode_active)
    property bool ntfyConfigured: !!(settings && settings.ntfy_topic)

    function normalizeTheme(v) {
        var t = String(v || "dark").toLowerCase().replace(/_/g, "-").trim();
        if (t === "deep sea" || t === "sea") return "deep-sea";
        var valid = ["dark", "light", "deep-sea", "contrast"];
        for (var i = 0; i < valid.length; i++) {
            if (t === valid[i]) return t;
        }
        return "dark";
    }

    function refreshNow() {
        var r = ShellApi.settings_get();
        if (r && r.ok) {
            settings = r.result || {};
            errorText = "";
        } else {
            errorText = (r && r.error) ? r.error : s("Lỗi tải cài đặt", "Settings load failed");
        }
    }

    function setLangValue(v) {
        if (v !== "VN" && v !== "EN") return;
        var s2 = {};
        for (var k in settings) s2[k] = settings[k];
        s2.lang = v;
        settings = s2;
        Theme.setLang(v);
    }

    function setThemeValue(v) {
        var s2 = {};
        for (var k in settings) s2[k] = settings[k];
        s2.theme = v;
        settings = s2;
        Theme.setTheme(v);
    }

    function setGhostValue(v) {
        var s2 = {};
        for (var k in settings) s2[k] = settings[k];
        s2.ghost_mode_active = v;
        settings = s2;
    }

    function saveNow() {
        if (saving) return;
        saving = true;
        errorText = "";
        savedMsg = "";
        var payload = { lang: langValue, theme: themeValue, ghost_mode_active: ghostActive };
        var r = ShellApi.settings_update(JSON.stringify(payload));
        if (r && r.ok) {
            savedMsg = s("Đã lưu (chỉ các trường cho phép).", "Saved (whitelisted fields only).");
            refreshNow();
        } else {
            errorText = (r && r.error) ? r.error : s("Lưu thất bại", "Save failed");
        }
        saving = false;
    }

    function resetTheme() {
        setThemeValue("dark");
    }

    Component.onCompleted: refreshNow()

    // ════════════════════════════════════════════════════════════════
    // LAYOUT
    // ════════════════════════════════════════════════════════════════
    Column {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 18
        spacing: 0

        // ── 1. Header row ──
        Item {
            width: parent.width
            height: 56
            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: root.s("TÙY CHỌN", "PREFERENCES")
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 2
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Cài đặt", "Settings")
                    font.pixelSize: 22
                    font.bold: true
                    color: root.pal.text
                }
            }
        }

        // ── 2. Error banner ──
        Rectangle {
            width: parent.width
            height: root.errorText !== "" ? 44 : 0
            visible: root.errorText !== ""
            radius: 8
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            clip: true
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                spacing: 10
                Rectangle {
                    width: errBadge.implicitWidth + 16
                    height: 20
                    radius: 4
                    color: Qt.rgba(root.danger.r, root.danger.g, root.danger.b, 0.15)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        id: errBadge
                        text: "ERROR"
                        font.pixelSize: 10
                        font.bold: true
                        font.letterSpacing: 1
                        color: "#e5534b"
                        anchors.centerIn: parent
                    }
                }
                Text {
                    text: root.errorText
                    font.pixelSize: 12
                    color: root.pal.text
                    elide: Text.ElideRight
                    width: root.width - 120
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // ── 3. Saved hint ──
        Text {
            width: parent.width
            height: root.savedMsg !== "" ? 18 : 0
            visible: root.savedMsg !== ""
            text: root.savedMsg
            font.pixelSize: 12
            color: root.pal.accent
        }

        // ── 4. General panel ──
        Rectangle {
            width: parent.width
            height: 230
            radius: 14
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            clip: true
            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                Text {
                    text: root.s("Chung", "General")
                    font.pixelSize: 15
                    font.bold: true
                    color: root.pal.text
                }

                // Row 1: Language
                Row {
                    spacing: 12
                    Text {
                        text: root.s("Ngôn ngữ", "Language")
                        font.pixelSize: 13
                        color: root.pal.text
                        width: 140
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    ComboBox {
                        id: langCombo
                        width: 140
                        model: ["VN", "EN"]
                        currentIndex: root.langValue === "VN" ? 0 : 1
                        onActivated: root.setLangValue(currentText)
                    }
                    Text {
                        text: root.s("Tiếng Việt / English", "Vietnamese / English")
                        font.pixelSize: 11
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Row 2: Theme
                Row {
                    spacing: 12
                    Text {
                        text: root.s("Giao diện", "Theme")
                        font.pixelSize: 13
                        color: root.pal.text
                        width: 140
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    ComboBox {
                        id: themeCombo
                        width: 140
                        model: ["dark", "deep-sea", "light", "contrast"]
                        currentIndex: {
                            if (root.themeValue === "contrast") return 3;
                            if (root.themeValue === "light") return 2;
                            if (root.themeValue === "deep-sea") return 1;
                            return 0;
                        }
                        onActivated: root.setThemeValue(currentText)
                    }
                    Text {
                        text: root.s("Dark / Deep sea / Light / Contrast")
                        font.pixelSize: 11
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Row 3: Ghost mode
                Row {
                    spacing: 12
                    Text {
                        text: root.s("Chế độ ẩn", "Ghost mode")
                        font.pixelSize: 13
                        color: root.pal.text
                        width: 140
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    CheckBox {
                        checked: root.ghostActive
                        onToggled: root.setGhostValue(checked)
                    }
                    Text {
                        text: root.s("Ẩn cửa sổ MT5 khi bot chạy", "Hide MT5 windows while the bot runs")
                        font.pixelSize: 11
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Row 4: ntfy_topic status
                Text {
                    text: "ntfy_topic: " + (root.ntfyConfigured ? s("đã cấu hình \u2713", "configured \u2713") : s("chưa đặt", "not set")) + s(" (giá trị ẩn)", " (value hidden)")
                    font.pixelSize: 11
                    font.family: "Consolas"
                    color: root.pal.muted
                }
            }
        }

        // ── 5. Actions Row ──
        Row {
            spacing: 8
            Rectangle {
                width: saveLabel.implicitWidth + 20
                height: 28
                radius: 8
                color: root.pal.accent
                border.color: root.pal.accent
                border.width: 1
                opacity: root.saving ? 0.6 : 1.0
                Text {
                    id: saveLabel
                    text: root.saving ? s("Đang lưu\u2026", "Saving\u2026") : root.s("Lưu", "Save")
                    font.pixelSize: 11
                    font.bold: true
                    color: "#ffffff"
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: !root.saving
                    onClicked: root.saveNow()
                }
            }
            Rectangle {
                width: reloadLabel.implicitWidth + 20
                height: 28
                radius: 8
                color: "transparent"
                border.color: root.pal.border
                border.width: 1
                Text {
                    id: reloadLabel
                    text: root.s("Tải lại", "Reload")
                    font.pixelSize: 11
                    font.bold: true
                    color: root.pal.text
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.refreshNow()
                }
            }
            Rectangle {
                width: resetLabel.implicitWidth + 20
                height: 28
                radius: 8
                color: "transparent"
                border.color: root.pal.border
                border.width: 1
                Text {
                    id: resetLabel
                    text: root.s("Đặt lại giao diện", "Reset theme")
                    font.pixelSize: 11
                    font.bold: true
                    color: root.pal.text
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.resetTheme()
                }
            }
        }

        // ── 6. About panel ──
        Rectangle {
            width: parent.width
            height: 150
            radius: 14
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            clip: true
            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 4
                Text {
                    text: root.s("Thông tin / bản build", "About / Build")
                    font.pixelSize: 15
                    font.bold: true
                    color: root.pal.text
                }
                Text { text: "OAK Manager"; font.pixelSize: 12; font.family: "Consolas"; color: root.pal.muted }
                Text { text: "Qt Quick + PySide6 + oak-core"; font.pixelSize: 12; font.family: "Consolas"; color: root.pal.muted }
                Text { text: "License: MIT \u00A9 2026 QKP"; font.pixelSize: 12; font.family: "Consolas"; color: root.pal.muted }
                Text { text: root.s("Giao thức", "Protocol") + ": v1"; font.pixelSize: 12; font.family: "Consolas"; color: root.pal.muted }
                Text { text: root.s("Phím tắt", "Shortcuts") + ": Ctrl+1..8 \u00B7 Ctrl+R/F5 \u00B7 Ctrl+S \u00B7 Esc"; font.pixelSize: 12; font.family: "Consolas"; color: root.pal.muted }
                Text { text: "THIRD_PARTY_NOTICES.md"; font.pixelSize: 11; font.family: "Consolas"; color: root.pal.muted }
            }
        }
    }
}
