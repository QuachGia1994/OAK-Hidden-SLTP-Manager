// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Copy"
    color: "transparent"
    anchors.fill: parent

    readonly property var pal: DesignTokens.palette(Theme.currentTheme)
    readonly property color okGreen: root.pal.accent
    property var profileNames: []
    property string selectedProfile: ""
    property var sltp: ({})
    property var copy: ({})
    property bool exists: false
    property bool busyLoading: false
    property bool saving: false
    property string errorText: ""
    property string noticeText: ""
    property string savedMsg: ""

    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    function refreshNow() {
        busyLoading = true;
        if (selectedProfile === "") {
            var plist = Api.list_profiles();
            if (plist && plist.length > 0) {
                profileNames = plist.map(function(p) { return p.profile_name; });
                if (selectedProfile === "" && profileNames.length > 0) {
                    selectedProfile = profileNames[0];
                }
            }
            if (selectedProfile === "") {
                errorText = s("Chọn hồ sơ.", "Select a profile.");
                busyLoading = false;
                return;
            }
        }
        var a = ShellApi.sltp_get(selectedProfile);
        var b = ShellApi.copy_get(selectedProfile);
        var plist2 = Api.list_profiles();
        if (plist2 && plist2.length > 0) {
            profileNames = plist2.map(function(p) { return p.profile_name; });
        }
        if (a.ok) {
            sltp = a.result.sltp || {};
            exists = a.result.exists || false;
        } else {
            errorText = a.error || "";
        }
        if (b.ok) {
            copy = b.result.copy || {};
        } else {
            errorText = b.error || "";
        }
        busyLoading = false;
    }

    function selectProfile(name) {
        selectedProfile = name;
        savedMsg = "";
        refreshNow();
    }

    function saveAll() {
        if (saving) return;
        if (selectedProfile === "") return;
        saving = true;
        savedMsg = "";
        errorText = "";
        var su = {
            visible_sltp: sltp.visible_sltp,
            sl: sltp.sl,
            tp: sltp.tp,
            gold_sl: sltp.gold_sl,
            gold_tp: sltp.gold_tp,
            use_balance_sltp: sltp.use_balance_sltp,
            balance_sl_pct: sltp.balance_sl_pct,
            balance_tp_pct: sltp.balance_tp_pct,
            partial_r: sltp.partial_r,
            partial_pct: sltp.partial_pct,
            auto_be: sltp.auto_be,
            magic: sltp.magic
        };
        var cu = {
            copy_role: copy.copy_role,
            copy_channel: copy.copy_channel,
            copy_max_daily_trades: copy.copy_max_daily_trades,
            copy_max_lot_per_trade: copy.copy_max_lot_per_trade,
            copy_max_exposure: copy.copy_max_exposure,
            copy_kill_switch: copy.copy_kill_switch,
            copy_stale_threshold: copy.copy_stale_threshold,
            copy_ignore_list: copy.copy_ignore_list,
            copy_stealth: copy.copy_stealth,
            copy_max_one: copy.copy_max_one,
            copy_lot_mode: copy.copy_lot_mode,
            copy_lot_value: copy.copy_lot_value
        };
        var r1 = ShellApi.sltp_update(selectedProfile, JSON.stringify(su));
        var r2 = ShellApi.copy_update(selectedProfile, JSON.stringify(cu));
        saving = false;
        if (r1.ok && r2.ok) {
            savedMsg = s("Đã lưu cấu hình " + selectedProfile + ".", "Saved config for " + selectedProfile + ".");
        } else {
            errorText = (!r1.ok ? r1.error : "") + (!r2.ok ? (" " + r2.error) : "");
        }
        refreshNow();
    }

    Component.onCompleted: refreshNow()

    // ══════════════════════════════════════════════════════════════
    // LAYOUT
    // ══════════════════════════════════════════════════════════════
    Column {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.topMargin: 16
        spacing: 10

        // ── Header ──
        Item {
            width: parent.width
            height: 44
            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: root.s("CẤU HÌNH HỒ SƠ", "PROFILE CONFIG")
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Sao chép", "Copy")
                    font.pixelSize: 20
                    font.bold: true
                    color: root.pal.text
                }
            }
            Item { width: parent.width - 300; height: 1 }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Text {
                    text: root.savedMsg
                    font.pixelSize: 12
                    color: root.okGreen
                    visible: root.savedMsg !== ""
                    anchors.verticalCenter: parent.verticalCenter
                }
                Rectangle {
                    width: 90
                    height: 28
                    radius: 8
                    color: "transparent"
                    border.color: root.pal.border
                    border.width: 1
                    objectName: "copyRefreshBtn"
                    Text {
                        text: root.s("Làm mới", "Refresh")
                        font.pixelSize: 12
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
                    width: 70
                    height: 28
                    radius: 8
                    color: root.saving ? Qt.rgba(root.pal.accent.r, root.pal.accent.g, root.pal.accent.b, 0.5) : root.pal.accent
                    border.color: root.pal.accent
                    border.width: 1
                    objectName: "copySaveBtn"
                    Text {
                        text: root.s("Lưu", "Save")
                        font.pixelSize: 12
                        font.bold: true
                        color: "#ffffff"
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: !root.saving
                        onClicked: root.saveAll()
                    }
                }
            }
        }

        // ── Error banner ──
        Rectangle {
            width: parent.width
            height: root.errorText !== "" ? 36 : 0
            visible: root.errorText !== ""
            radius: 8
            color: Qt.rgba(229/255, 72/255, 77/255, 0.12)
            border.color: "#e5484d"
            border.width: 1
            objectName: "errorBanner"
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                spacing: 8
                Text {
                    text: root.s("LỖI", "ERROR")
                    font.pixelSize: 12
                    font.bold: true
                    color: "#e5484d"
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: root.errorText
                    font.pixelSize: 12
                    color: "#e5484d"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // ── Notice banner ──
        Rectangle {
            width: parent.width
            height: root.noticeText !== "" ? 36 : 0
            visible: root.noticeText !== ""
            radius: 8
            color: Qt.rgba(root.okGreen.r, root.okGreen.g, root.okGreen.b, 0.12)
            border.color: root.okGreen
            border.width: 1
            objectName: "noticeBanner"
            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                text: root.noticeText
                font.pixelSize: 12
                color: root.okGreen
            }
        }

        // ── Profile selector ──
        Row {
            visible: root.profileNames.length > 0
            spacing: 8
            Text {
                text: root.s("Hồ sơ", "Profile")
                font.pixelSize: 11
                color: root.pal.muted
                anchors.verticalCenter: parent.verticalCenter
            }
            Repeater {
                model: root.profileNames
                Rectangle {
                    width: profileChipText.implicitWidth + 16
                    height: 24
                    radius: 6
                    color: "transparent"
                    border.color: root.selectedProfile === modelData ? root.pal.accent : root.pal.border
                    border.width: 1
                    objectName: "copyProfileChip"
                    Text {
                        id: profileChipText
                        text: modelData
                        font.pixelSize: 11
                        color: root.selectedProfile === modelData ? root.pal.accent : root.pal.text
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.selectProfile(modelData)
                    }
                }
            }
        }

        // ── Two-panel content ──
        Flickable {
            width: parent.width
            height: parent.height - 44 - (root.errorText !== "" ? 46 : 0) - (root.noticeText !== "" ? 46 : 0) - 34 - 16
            contentHeight: panelsRow.height
            clip: true

            Row {
                id: panelsRow
                width: parent.width
                spacing: 12
                height: 640

                // ═══ LEFT PANEL — SL/TP ═══
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: 640
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    radius: 8
                    clip: true
                    objectName: "sltpPanel"

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        Text {
                            text: root.s("SL/TP Ẩn", "Hidden SL/TP")
                            font.pixelSize: 14
                            font.bold: true
                            color: root.pal.text
                        }

                        // visible_sltp
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.sltp.visible_sltp === true
                                onToggled: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.visible_sltp = checked; root.sltp = s2; }
                            }
                            Text {
                                text: root.s("Hiện SL/TP", "Show SL/TP")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // sl
                        Column { spacing: 2
                            Text { text: root.s("SL", "SL"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_sl.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_sl; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.sl !== null && root.sltp.sl !== undefined ? String(root.sltp.sl) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.sl = text; root.sltp = s2; }
                                }
                            }
                        }

                        // tp
                        Column { spacing: 2
                            Text { text: root.s("TP", "TP"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_tp.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_tp; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.tp !== null && root.sltp.tp !== undefined ? String(root.sltp.tp) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.tp = text; root.sltp = s2; }
                                }
                            }
                        }

                        // gold_sl
                        Column { spacing: 2
                            Text { text: root.s("Gold SL", "Gold SL"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_gold_sl.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_gold_sl; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.gold_sl !== null && root.sltp.gold_sl !== undefined ? String(root.sltp.gold_sl) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.gold_sl = text; root.sltp = s2; }
                                }
                            }
                        }

                        // gold_tp
                        Column { spacing: 2
                            Text { text: root.s("Gold TP", "Gold TP"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_gold_tp.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_gold_tp; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.gold_tp !== null && root.sltp.gold_tp !== undefined ? String(root.sltp.gold_tp) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.gold_tp = text; root.sltp = s2; }
                                }
                            }
                        }

                        // use_balance_sltp
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.sltp.use_balance_sltp === true
                                onToggled: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.use_balance_sltp = checked; root.sltp = s2; }
                            }
                            Text {
                                text: root.s("SL/TP theo số dư", "Balance-based SL/TP")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // balance_sl_pct
                        Column { spacing: 2
                            Text { text: root.s("SL % số dư", "Balance SL %"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_balance_sl_pct.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_balance_sl_pct; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.balance_sl_pct !== null && root.sltp.balance_sl_pct !== undefined ? String(root.sltp.balance_sl_pct) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.balance_sl_pct = text; root.sltp = s2; }
                                }
                            }
                        }

                        // balance_tp_pct
                        Column { spacing: 2
                            Text { text: root.s("TP % số dư", "Balance TP %"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_balance_tp_pct.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_balance_tp_pct; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.balance_tp_pct !== null && root.sltp.balance_tp_pct !== undefined ? String(root.sltp.balance_tp_pct) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.balance_tp_pct = text; root.sltp = s2; }
                                }
                            }
                        }

                        // partial_r
                        Column { spacing: 2
                            Text { text: root.s("R chốt 1 phần", "Partial R"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_partial_r.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_partial_r; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.partial_r !== null && root.sltp.partial_r !== undefined ? String(root.sltp.partial_r) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.partial_r = text; root.sltp = s2; }
                                }
                            }
                        }

                        // partial_pct
                        Column { spacing: 2
                            Text { text: root.s("% chốt 1 phần", "Partial %"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_partial_pct.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_partial_pct; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.partial_pct !== null && root.sltp.partial_pct !== undefined ? String(root.sltp.partial_pct) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.partial_pct = text; root.sltp = s2; }
                                }
                            }
                        }

                        // auto_be
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.sltp.auto_be === true
                                onToggled: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.auto_be = checked; root.sltp = s2; }
                            }
                            Text {
                                text: root.s("BE tự động", "Auto break-even")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // magic
                        Column { spacing: 2
                            Text { text: "Magic"; font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: sltpFields.width - 12; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_magic.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_magic; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.sltp.magic !== null && root.sltp.magic !== undefined ? String(root.sltp.magic) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.sltp) s2[k] = root.sltp[k]; s2.magic = text; root.sltp = s2; }
                                }
                            }
                        }

                        // Invisible id used by sltpFields width binding
                        Item { id: sltpFields; width: parent.width; height: 0 }
                    }
                }

                // ═══ RIGHT PANEL — Copy Trading ═══
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: 640
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    radius: 8
                    clip: true
                    objectName: "copyPanel"

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 6

                        // Title + badge row
                        Row {
                            width: parent.width
                            spacing: 8
                            Text {
                                text: root.s("Copy Trading", "Copy Trading")
                                font.pixelSize: 14
                                font.bold: true
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Rectangle {
                                visible: root.copy.copy_kill_switch === true
                                width: killSwitchBadge.implicitWidth + 12
                                height: 18
                                radius: 4
                                color: "transparent"
                                border.color: "#e5484d"
                                border.width: 1
                                objectName: "killSwitchBadge"
                                Text {
                                    id: killSwitchBadge
                                    text: root.s("NGẮT KHẨN", "KILL SWITCH ON")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#e5484d"
                                    anchors.centerIn: parent
                                }
                            }
                            Rectangle {
                                visible: root.copy.copy_kill_switch !== true
                                width: armedBadge.implicitWidth + 12
                                height: 18
                                radius: 4
                                color: "transparent"
                                border.color: root.pal.accent
                                border.width: 1
                                objectName: "armedBadge"
                                Text {
                                    id: armedBadge
                                    text: root.s("SẴN SÀNG", "ARMED")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: root.pal.accent
                                    anchors.centerIn: parent
                                }
                            }
                        }

                        // copy_role
                        Column { spacing: 2
                            Text { text: root.s("Vai trò", "Role"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_role.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_role; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_role !== null && root.copy.copy_role !== undefined ? String(root.copy.copy_role) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_role = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_channel
                        Column { spacing: 2
                            Text { text: root.s("Kênh", "Channel"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_channel.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_channel; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_channel !== null && root.copy.copy_channel !== undefined ? String(root.copy.copy_channel) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_channel = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_max_daily_trades
                        Column { spacing: 2
                            Text { text: root.s("Lệnh/ngày max", "Max daily trades"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_max_daily_trades.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_max_daily_trades; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_max_daily_trades !== null && root.copy.copy_max_daily_trades !== undefined ? String(root.copy.copy_max_daily_trades) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_max_daily_trades = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_max_lot_per_trade
                        Column { spacing: 2
                            Text { text: root.s("Lot max/lệnh", "Max lot per trade"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_max_lot_per_trade.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_max_lot_per_trade; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_max_lot_per_trade !== null && root.copy.copy_max_lot_per_trade !== undefined ? String(root.copy.copy_max_lot_per_trade) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_max_lot_per_trade = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_max_exposure
                        Column { spacing: 2
                            Text { text: root.s("Exposure max", "Max exposure"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_max_exposure.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_max_exposure; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_max_exposure !== null && root.copy.copy_max_exposure !== undefined ? String(root.copy.copy_max_exposure) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_max_exposure = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_kill_switch
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.copy.copy_kill_switch === true
                                onToggled: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_kill_switch = checked; root.copy = s2; }
                            }
                            Text {
                                text: root.s("Kill switch (ngắt khẩn)", "Kill switch")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // copy_stale_threshold
                        Column { spacing: 2
                            Text { text: root.s("Stale (phút)", "Stale threshold"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_stale_threshold.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_stale_threshold; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_stale_threshold !== null && root.copy.copy_stale_threshold !== undefined ? String(root.copy.copy_stale_threshold) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_stale_threshold = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_ignore_list (wider)
                        Column { spacing: 2
                            Text { text: root.s("Danh sách bỏ qua", "Ignore list"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_ignore_list.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_ignore_list; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_ignore_list !== null && root.copy.copy_ignore_list !== undefined ? String(root.copy.copy_ignore_list) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_ignore_list = text; root.copy = s2; }
                                }
                            }
                        }

                        // copy_stealth
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.copy.copy_stealth === true
                                onToggled: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_stealth = checked; root.copy = s2; }
                            }
                            Text {
                                text: root.s("Stealth", "Stealth")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // copy_max_one
                        Row {
                            spacing: 8
                            CheckBox {
                                checked: root.copy.copy_max_one === true
                                onToggled: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_max_one = checked; root.copy = s2; }
                            }
                            Text {
                                text: root.s("Chỉ 1 lệnh cùng mã", "Max one per symbol")
                                font.pixelSize: 12
                                color: root.pal.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // copy_lot_mode chip selector
                        Row {
                            spacing: 8
                            Text {
                                text: root.s("Lot mode", "Lot mode")
                                font.pixelSize: 11
                                color: root.pal.muted
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Repeater {
                                model: ["Fixed", "Percent"]
                                Rectangle {
                                    width: lotModeChipText.implicitWidth + 16
                                    height: 24
                                    radius: 6
                                    color: "transparent"
                                    border.color: root.copy.copy_lot_mode === modelData ? root.pal.accent : root.pal.border
                                    border.width: 1
                                    objectName: "copyLotModeChip"
                                    Text {
                                        id: lotModeChipText
                                        text: modelData
                                        font.pixelSize: 11
                                        color: root.copy.copy_lot_mode === modelData ? root.pal.accent : root.pal.text
                                        anchors.centerIn: parent
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_lot_mode = modelData; root.copy = s2; }
                                    }
                                }
                            }
                            objectName: "copyLotMode"
                        }

                        // copy_lot_value
                        Column { spacing: 2
                            Text { text: root.s("Lot", "Lot value"); font.pixelSize: 11; color: root.pal.muted }
                            Rectangle { width: parent.width; height: 26; radius: 4; color: root.pal.windowBg; border.color: fld_copy_lot_value.activeFocus ? root.pal.accent : root.pal.border; border.width: 1
                                TextInput { id: fld_copy_lot_value; anchors.fill: parent; anchors.margins: 4; color: root.pal.text; font.pixelSize: 12; selectByMouse: true; text: root.copy.copy_lot_value !== null && root.copy.copy_lot_value !== undefined ? String(root.copy.copy_lot_value) : ""
                                    onTextEdited: { var s2 = {}; for (var k in root.copy) s2[k] = root.copy[k]; s2.copy_lot_value = text; root.copy = s2; }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
