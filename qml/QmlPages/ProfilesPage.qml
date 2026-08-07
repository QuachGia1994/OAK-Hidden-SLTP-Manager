// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Item {
    id: root
    objectName: "page_Profiles"

    // ── Palette (singletons registered globally by main.qml's QmlDesign import) ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    // ── i18n helper ──
    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    // ── Test-accessible helpers (root-level properties for QQmlExpression) ──
    readonly property int profileCount: profilesModel ? profilesModel.count : 0
    readonly property var api: Api

    // ── State ──
    property var profiles: []
    property string selectedName: ""
    property var draft: ({})
    property bool dirty: false
    property bool deleteArmed: false
    property string errorText: ""
    property string notice: ""
    property bool tokenConfigured: false
    property bool keyringAvailable: false
    property string tokenInput: ""
    property bool busy: false

    // ── Internal helpers ──
    function reload() {
        var list = Api.list_profiles();
        if (list === undefined || list === null) return;
        profiles = list;
        rebuildModel();
        // Keep selection if still present
        if (selectedName !== "") {
            var found = false;
            for (var i = 0; i < profiles.length; i++) {
                if (profiles[i].profile_name === selectedName) { found = true; break; }
            }
            if (!found && profiles.length > 0) {
                selectedName = profiles[0].profile_name;
                loadDraft();
            }
        } else if (profiles.length > 0) {
            selectedName = profiles[0].profile_name;
            loadDraft();
        }
        errorText = "";
        if (selectedName !== "") loadSecretStatus();
    }

    function rebuildModel() {
        profilesModel.clear();
        for (var i = 0; i < profiles.length; i++) {
            var p = profiles[i];
            profilesModel.append({
                profile_name: p.profile_name || "",
                status: p.status || "stopped",
                pid: p.pid !== undefined ? p.pid : null,
                path: p.path || "",
                copy_role: p.copy_role || "None",
                visible_sltp: p.visible_sltp || false,
                copy_kill_switch: p.copy_kill_switch || false,
                magic: p.magic !== undefined ? p.magic : -1,
                symbol: p.symbol || "",
                mt5_portable: p.mt5_portable || false,
                tele_chat: p.tele_chat || "",
                tele_admin: p.tele_admin || ""
            });
        }
    }

    function loadDraft() {
        for (var i = 0; i < profiles.length; i++) {
            var p = profiles[i];
            if (p.profile_name === selectedName) {
                draft = {
                    profile_name: p.profile_name || "",
                    path: p.path || "",
                    magic: p.magic !== undefined ? String(p.magic) : "-1",
                    symbol: p.symbol || "",
                    mt5_portable: p.mt5_portable || false,
                    tele_chat: p.tele_chat || "",
                    tele_admin: p.tele_admin || ""
                };
                dirty = false;
                deleteArmed = false;
                return;
            }
        }
        draft = {};
    }

    function save() {
        if (selectedName === "") {
            notice = s("Chọn profile trước khi lưu", "Select a profile before saving");
            return;
        }
        // Validate magic
        var magicStr = String(draft.magic || "").trim();
        if (magicStr !== "" && !/^-?\d+$/.test(magicStr)) {
            errorText = s("Magic phải là số nguyên", "Magic must be an integer");
            return;
        }
        var updates = {
            profile_name: draft.profile_name,
            path: draft.path,
            magic: magicStr !== "" ? parseInt(magicStr, 10) : -1,
            symbol: draft.symbol,
            mt5_portable: draft.mt5_portable,
            tele_chat: draft.tele_chat,
            tele_admin: draft.tele_admin
        };
        var result = Api.update_profile(selectedName, JSON.stringify(updates));
        if (result.ok) {
            selectedName = result.result.profile_name;
            dirty = false;
            notice = s("Đã lưu profile", "Profile saved");
            reload();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function startStop(name, running) {
        busy = true;
        var result;
        if (running) {
            result = Api.stop_profile(name);
        } else {
            result = Api.start_profile(name);
        }
        busy = false;
        if (result.ok) {
            reload();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function addNew() {
        var base = "NewProfile";
        var existing = {};
        for (var i = 0; i < profiles.length; i++) {
            existing[profiles[i].profile_name] = true;
        }
        var name = base;
        var counter = 2;
        while (existing[name]) {
            name = base + " " + counter;
            counter++;
        }
        var result = Api.add_profile(name);
        if (result.ok) {
            selectedName = name;
            notice = s("Đã tạo profile", "Profile created");
            reload();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function duplicate() {
        if (selectedName === "") {
            notice = s("Chọn một profile để nhân bản", "Select a profile to duplicate");
            return;
        }
        var result = Api.duplicate_profile(selectedName);
        if (result.ok) {
            selectedName = result.result.profile_name;
            notice = s("Đã nhân bản profile", "Profile duplicated");
            reload();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function deleteSelected() {
        if (selectedName === "") return;
        if (!deleteArmed) {
            deleteArmed = true;
            notice = s("Bấm Xóa lần nữa để xác nhận: " + selectedName, "Click Delete again to confirm: " + selectedName);
            return;
        }
        busy = true;
        var result = Api.delete_profile(selectedName);
        busy = false;
        if (result.ok) {
            deleteArmed = false;
            selectedName = "";
            notice = s("Đã xóa profile", "Profile deleted");
            reload();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function loadSecretStatus() {
        if (selectedName === "") return;
        var result = Api.secret_status(selectedName);
        if (result.ok) {
            tokenConfigured = result.result.tele_token_configured || false;
            keyringAvailable = result.result.keyring_available || false;
        }
        tokenInput = "";
    }

    function saveToken() {
        var token = tokenInput.trim();
        if (token === "") {
            errorText = s("Nhập token Telegram", "Enter a Telegram token");
            return;
        }
        busy = true;
        var result = Api.set_tele_token(selectedName, token);
        busy = false;
        if (result.ok) {
            tokenInput = "";
            notice = s("Đã lưu token", "Token saved");
            loadSecretStatus();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function clearToken() {
        busy = true;
        var result = Api.clear_tele_token(selectedName);
        busy = false;
        if (result.ok) {
            tokenInput = "";
            notice = s("Đã xóa token", "Token cleared");
            loadSecretStatus();
        } else {
            errorText = result.error || "Unknown error";
        }
    }

    function pathSegment(fullPath) {
        if (!fullPath) return "MT5";
        var parts = fullPath.replace(/\\/g, "/").split("/");
        return parts[parts.length - 1] || "MT5";
    }

    // ── Auto-reload on timer ──
    Component.onCompleted: reload()
    Timer { interval: 3000; running: true; repeat: true; onTriggered: reload() }

    // ── Layout ──
    Column {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        // ── Row 1: Header ──
        Row {
            width: parent.width
            height: 40
            spacing: 12

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: s("HỒ SƠ", "PROFILES")
                    font.pixelSize: 24
                    font.bold: true
                    color: root.pal.text
                }
                Text {
                    text: s("Quản lý profile & trạng thái worker", "Manage profiles & worker status")
                    font.pixelSize: 12
                    color: root.pal.muted
                }
            }

            Item { width: parent.width - 88 - 12; height: 1 }

            Rectangle {
                width: 88
                height: 30
                radius: 8
                color: "transparent"
                border.color: root.pal.border
                border.width: 1
                Text {
                    text: s("Làm mới", "Refresh")
                    font.pixelSize: 12
                    color: root.pal.text
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: reload()
                }
            }
        }

        // ── Row 2: Error banner ──
        Rectangle {
            width: parent.width
            height: errorText !== "" ? 36 : 0
            visible: errorText !== ""
            radius: 8
            color: Qt.rgba(229/255, 72/255, 77/255, 0.12)
            border.color: "#e5484d"
            border.width: 1
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                spacing: 8
                Text {
                    text: s("LỖI", "ERROR")
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

        // ── Row 3: Notice ──
        Text {
            width: parent.width
            text: root.notice
            visible: root.notice !== ""
            font.pixelSize: 12
            color: root.pal.muted
        }

        // ── Row 4: Content ──
        Item {
            width: parent.width
            height: parent.height - 40 - (errorText !== "" ? 48 : 0) - (notice !== "" ? 24 : 0) - 24

            Row {
                anchors.fill: parent
                spacing: 18

                // ── Left panel: Profile Map ──
                Rectangle {
                    width: 330
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        // Header
                        Row {
                            width: parent.width
                            height: 20
                            Text {
                                id: mapLabel
                                text: s("BẢN ĐỒ PROFILE", "PROFILE MAP")
                                font.pixelSize: 12
                                font.bold: true
                                font.letterSpacing: 2
                                color: root.pal.muted
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Item { width: parent.width - mapLabel.width - countText.width - 12; height: 1 }
                            Text {
                                id: countText
                                text: root.profiles.length
                                font.pixelSize: 12
                                font.family: "monospace"
                                color: root.pal.muted
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // ListView
                        ListView {
                            id: profilesList
                            width: parent.width
                            height: parent.height - 30 - (profilesModel.count === 0 ? 30 : 0)
                            model: ListModel { id: profilesModel }
                            clip: true
                            spacing: 8

                            delegate: Rectangle {
                                width: profilesList.width
                                height: 86
                                radius: 14
                                color: model.profile_name === root.selectedName ? root.pal.navActiveBg : root.pal.surface
                                border.color: model.profile_name === root.selectedName ? root.pal.accent : root.pal.border
                                border.width: 1

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 6

                                    // Row 1: status dot + name + meta
                                    Row {
                                        width: parent.width
                                        spacing: 8
                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: model.status === "running" ? root.pal.accent : (model.status === "exited" ? "#e5484d" : root.pal.muted)
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            id: cardNameText
                                            text: model.profile_name
                                            width: parent.width - 12 - 110 - 16
                                            font.pixelSize: 14
                                            font.bold: true
                                            color: root.pal.text
                                            anchors.verticalCenter: parent.verticalCenter
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: model.pid ? ("PID " + model.pid) : pathSegment(model.path)
                                            width: 110
                                            font.pixelSize: 11
                                            font.family: "monospace"
                                            color: root.pal.muted
                                            anchors.verticalCenter: parent.verticalCenter
                                            elide: Text.ElideRight
                                            horizontalAlignment: Text.AlignRight
                                        }
                                    }

                                    // Row 2: badges
                                    Row {
                                        spacing: 6
                                        Rectangle {
                                            width: badgeCopyRole.width + 12
                                            height: 18
                                            radius: 9
                                            color: Qt.rgba(0.5, 0.5, 0.5, 0.2)
                                            Text {
                                                id: badgeCopyRole
                                                text: model.copy_role
                                                font.pixelSize: 10
                                                color: root.pal.muted
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            width: badgeSltp.width + 12
                                            height: 18
                                            radius: 9
                                            color: Qt.rgba(0.5, 0.5, 0.5, 0.2)
                                            Text {
                                                id: badgeSltp
                                                text: model.visible_sltp ? s("SL/TP Có", "SL/TP On") : s("SL/TP Không", "SL/TP Off")
                                                font.pixelSize: 10
                                                color: root.pal.muted
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            visible: model.copy_kill_switch
                                            width: badgeKill.width + 12
                                            height: 18
                                            radius: 9
                                            color: Qt.rgba(229/255, 72/255, 77/255, 0.3)
                                            Text {
                                                id: badgeKill
                                                text: "KILL"
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: "#e5484d"
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            visible: !model.copy_kill_switch
                                            width: badgeArmed.width + 12
                                            height: 18
                                            radius: 9
                                            color: Qt.rgba(47/255, 165/255, 114/255, 0.3)
                                            Text {
                                                id: badgeArmed
                                                text: "ARMED"
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: root.pal.accent
                                                anchors.centerIn: parent
                                            }
                                        }
                                    }

                                    // Row 3: action buttons
                                    Row {
                                        spacing: 6
                                        Rectangle {
                                            width: 60
                                            height: 24
                                            radius: 6
                                            color: model.profile_name === root.selectedName ? Qt.rgba(0.5, 0.5, 0.5, 0.3) : "transparent"
                                            border.color: root.pal.border
                                            border.width: 1
                                            Text {
                                                text: model.profile_name === root.selectedName ? s("Đã chọn", "Selected") : s("Sử dụng", "Use")
                                                font.pixelSize: 11
                                                color: model.profile_name === root.selectedName ? root.pal.muted : root.pal.text
                                                anchors.centerIn: parent
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: model.profile_name === root.selectedName ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                enabled: model.profile_name !== root.selectedName
                                                onClicked: {
                                                    root.selectedName = model.profile_name;
                                                    root.loadDraft();
                                                    root.loadSecretStatus();
                                                }
                                            }
                                        }
                                        Rectangle {
                                            width: 60
                                            height: 24
                                            radius: 6
                                            color: root.pal.accent
                                            visible: model.status !== "running"
                                            Text {
                                                text: s("Bắt đầu", "Start")
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#ffffff"
                                                anchors.centerIn: parent
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.startStop(model.profile_name, false)
                                            }
                                        }
                                        Rectangle {
                                            width: 60
                                            height: 24
                                            radius: 6
                                            color: "#e5484d"
                                            visible: model.status === "running"
                                            Text {
                                                text: s("Dừng", "Stop")
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#ffffff"
                                                anchors.centerIn: parent
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: root.startStop(model.profile_name, true)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            visible: profilesModel.count === 0
                            width: parent.width
                            text: s("Chưa có profile. Bấm Thêm mới để tạo.", "No profiles yet. Click Add new to create.")
                            font.pixelSize: 12
                            color: root.pal.muted
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // ── Right panel: Profile Editor ──
                Rectangle {
                    width: parent.width - 330 - 18
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12

                        // Header
                        Row {
                            width: parent.width
                            height: 36
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                Text {
                                    text: root.selectedName !== "" ? root.selectedName : s("Chưa chọn profile", "No profile selected")
                                    font.pixelSize: 16
                                    font.bold: true
                                    color: root.pal.text
                                }
                                Text {
                                    text: root.dirty ? s("Có thay đổi chưa lưu", "Unsaved changes") : s("Thay đổi được lưu vào profiles.json", "Changes are saved to profiles.json")
                                    font.pixelSize: 12
                                    color: root.pal.muted
                                }
                            }
                            Item { width: parent.width - 100 - 12; height: 1 }
                            Rectangle {
                                width: 80
                                height: 24
                                radius: 12
                                color: root.selectedName === "" ? Qt.rgba(0.5, 0.5, 0.5, 0.2)
                                    : (function() {
                                        for (var i = 0; i < root.profiles.length; i++) {
                                            if (root.profiles[i].profile_name === root.selectedName) {
                                                var st = root.profiles[i].status;
                                                if (st === "running") return root.pal.accent;
                                                if (st === "exited") return "#e5484d";
                                                return Qt.rgba(0.5, 0.5, 0.5, 0.3);
                                            }
                                        }
                                        return Qt.rgba(0.5, 0.5, 0.5, 0.3);
                                    })()
                                Text {
                                    text: {
                                        if (root.selectedName === "") return "IDLE";
                                        for (var i = 0; i < root.profiles.length; i++) {
                                            if (root.profiles[i].profile_name === root.selectedName) {
                                                var st = root.profiles[i].status;
                                                if (st === "running") return s("ĐANG CHẠY", "RUNNING");
                                                if (st === "exited") return s("THOÁT", "EXITED");
                                                return s("ĐÃ DỪNG", "STOPPED");
                                            }
                                        }
                                        return "IDLE";
                                    }
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#ffffff"
                                    anchors.centerIn: parent
                                }
                            }
                        }

                        // Actions row
                        Row {
                            spacing: 8
                            Rectangle {
                                width: saveBtnText.width + 20
                                height: 28
                                radius: 8
                                color: root.pal.accent
                                Text {
                                    id: saveBtnText
                                    text: s("Lưu", "Save")
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: "#ffffff"
                                    anchors.centerIn: parent
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: root.selectedName !== "" && !root.busy
                                    opacity: enabled ? 1.0 : 0.45
                                    onClicked: root.save()
                                }
                            }
                            Rectangle {
                                width: dupBtnText.width + 20
                                height: 28
                                radius: 8
                                color: "transparent"
                                border.color: root.pal.border
                                border.width: 1
                                Text {
                                    id: dupBtnText
                                    text: s("Nhân bản", "Duplicate")
                                    font.pixelSize: 12
                                    color: root.pal.text
                                    anchors.centerIn: parent
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: root.selectedName !== "" && !root.busy
                                    opacity: enabled ? 1.0 : 0.45
                                    onClicked: root.duplicate()
                                }
                            }
                            Rectangle {
                                width: addBtnText.width + 20
                                height: 28
                                radius: 8
                                color: "transparent"
                                border.color: root.pal.border
                                border.width: 1
                                Text {
                                    id: addBtnText
                                    text: s("Thêm mới", "Add new")
                                    font.pixelSize: 12
                                    color: root.pal.text
                                    anchors.centerIn: parent
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !root.busy
                                    opacity: enabled ? 1.0 : 0.45
                                    onClicked: root.addNew()
                                }
                            }
                            Rectangle {
                                width: delBtnText.width + 20
                                height: 28
                                radius: 8
                                color: root.deleteArmed ? "#e5484d" : "transparent"
                                border.color: "#e5484d"
                                border.width: 1
                                Text {
                                    id: delBtnText
                                    text: root.deleteArmed ? s("Xóa lần nữa để xác nhận", "Delete again to confirm") : s("Xóa", "Delete")
                                    font.pixelSize: 12
                                    font.bold: root.deleteArmed
                                    color: root.deleteArmed ? "#ffffff" : "#e5484d"
                                    anchors.centerIn: parent
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: root.selectedName !== "" && !root.busy
                                    opacity: enabled ? 1.0 : 0.45
                                    onClicked: root.deleteSelected()
                                }
                            }
                        }

                        // Fields (when profile selected)
                        Column {
                            visible: root.selectedName !== ""
                            width: parent.width
                            spacing: 10

                            // Profile name
                            Column {
                                width: parent.width
                                spacing: 4
                                Text {
                                    text: s("Tên profile", "Profile name")
                                    font.pixelSize: 12
                                    color: root.pal.muted
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 32
                                    radius: 8
                                    color: root.pal.surface
                                    border.color: nameInput.activeFocus ? root.pal.accent : root.pal.border
                                    border.width: 1
                                    TextInput {
                                        id: nameInput
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        color: root.pal.text
                                        font.pixelSize: 13
                                        text: root.draft.profile_name || ""
                                        onTextChanged: {
                                            if (root.draft.profile_name !== text) {
                                                root.draft.profile_name = text;
                                                root.dirty = true;
                                            }
                                        }
                                    }
                                }
                            }

                            // Path
                            Column {
                                width: parent.width
                                spacing: 4
                                Text {
                                    text: s("Đường dẫn terminal", "Terminal path")
                                    font.pixelSize: 12
                                    color: root.pal.muted
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 32
                                    radius: 8
                                    color: root.pal.surface
                                    border.color: pathInput.activeFocus ? root.pal.accent : root.pal.border
                                    border.width: 1
                                    TextInput {
                                        id: pathInput
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        color: root.pal.text
                                        font.pixelSize: 13
                                        text: root.draft.path || ""
                                        onTextChanged: {
                                            if (root.draft.path !== text) {
                                                root.draft.path = text;
                                                root.dirty = true;
                                            }
                                        }
                                    }
                                }
                            }

                            // Magic + Portable row
                            Row {
                                width: parent.width
                                spacing: 12

                                Column {
                                    width: parent.width * 0.6
                                    spacing: 4
                                    Text {
                                        text: s("Số magic", "Magic number")
                                        font.pixelSize: 12
                                        color: root.pal.muted
                                    }
                                    Rectangle {
                                        width: parent.width
                                        height: 32
                                        radius: 8
                                        color: root.pal.surface
                                        border.color: magicInput.activeFocus ? root.pal.accent : root.pal.border
                                        border.width: 1
                                        TextInput {
                                            id: magicInput
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            color: root.pal.text
                                            font.pixelSize: 13
                                            font.family: "monospace"
                                            text: root.draft.magic || ""
                                            onTextChanged: {
                                                if (root.draft.magic !== text) {
                                                    root.draft.magic = text;
                                                    root.dirty = true;
                                                }
                                            }
                                        }
                                    }
                                }

                                Column {
                                    width: parent.width * 0.4
                                    spacing: 4
                                    Text {
                                        text: s("Portable terminal", "Terminal di động")
                                        font.pixelSize: 12
                                        color: root.pal.muted
                                    }
                                    Rectangle {
                                        width: 28
                                        height: 28
                                        radius: 6
                                        color: root.pal.surface
                                        border.color: root.pal.border
                                        border.width: 1
                                        Rectangle {
                                            visible: root.draft.mt5_portable
                                            width: 16
                                            height: 16
                                            radius: 4
                                            color: root.pal.accent
                                            anchors.centerIn: parent
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.draft.mt5_portable = !root.draft.mt5_portable;
                                                root.dirty = true;
                                            }
                                        }
                                    }
                                }
                            }

                            // Symbol
                            Column {
                                width: parent.width
                                spacing: 4
                                Text {
                                    text: s("Lọc symbol", "Symbol filter")
                                    font.pixelSize: 12
                                    color: root.pal.muted
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 32
                                    radius: 8
                                    color: root.pal.surface
                                    border.color: symbolInput.activeFocus ? root.pal.accent : root.pal.border
                                    border.width: 1
                                    TextInput {
                                        id: symbolInput
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        color: root.pal.text
                                        font.pixelSize: 13
                                        text: root.draft.symbol || ""
                                        onTextChanged: {
                                            if (root.draft.symbol !== text) {
                                                root.draft.symbol = text;
                                                root.dirty = true;
                                            }
                                        }
                                    }
                                }
                            }

                            // ── Telegram sub-panel ──
                            Rectangle {
                                width: parent.width
                                height: teleColumn.height + 24
                                radius: 8
                                color: root.pal.surface
                                border.color: root.pal.border
                                border.width: 1

                                Column {
                                    id: teleColumn
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    // Header
                                    Row {
                                        width: parent.width
                                        Text {
                                            id: teleLabel
                                            text: "TELEGRAM"
                                            font.pixelSize: 12
                                            font.bold: true
                                            font.letterSpacing: 2
                                            color: root.pal.muted
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Item { width: parent.width - teleLabel.width - tokenBadge.width - keyringBadge.width - 12; height: 1 }
                                        Rectangle {
                                            id: tokenBadge
                                            width: badgeToken.width + 12
                                            height: 18
                                            radius: 9
                                            color: root.tokenConfigured ? root.pal.accent : Qt.rgba(0.5, 0.5, 0.5, 0.3)
                                            Text {
                                                id: badgeToken
                                                text: root.tokenConfigured ? s("TOKEN ĐÃ LƯU", "TOKEN SET") : s("CHƯA CÓ TOKEN", "NO TOKEN")
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: "#ffffff"
                                                anchors.centerIn: parent
                                            }
                                        }
                                        Rectangle {
                                            id: keyringBadge
                                            width: badgeKeyring.width + 12
                                            height: 18
                                            radius: 9
                                            color: root.keyringAvailable ? Qt.rgba(0.5, 0.5, 0.5, 0.3) : "#e5484d"
                                            Text {
                                                id: badgeKeyring
                                                text: root.keyringAvailable ? s("KEYRING SẴN SÀNG", "KEYRING OK") : s("KEYRING KHÔNG KHẢ DỤNG", "KEYRING DOWN")
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: root.keyringAvailable ? root.pal.muted : "#ffffff"
                                                anchors.centerIn: parent
                                            }
                                        }
                                    }

                                    // Chat ID
                                    Column {
                                        width: parent.width
                                        spacing: 4
                                        Text {
                                            text: s("Telegram chat", "Telegram chat")
                                            font.pixelSize: 12
                                            color: root.pal.muted
                                        }
                                        Rectangle {
                                            width: parent.width
                                            height: 28
                                            radius: 6
                                            color: root.pal.windowBg
                                            border.color: teleChatInput.activeFocus ? root.pal.accent : root.pal.border
                                            border.width: 1
                                            TextInput {
                                                id: teleChatInput
                                                anchors.fill: parent
                                                anchors.margins: 6
                                                color: root.pal.text
                                                font.pixelSize: 12
                                                text: root.draft.tele_chat || ""
                                                onTextChanged: {
                                                    if (root.draft.tele_chat !== text) {
                                                        root.draft.tele_chat = text;
                                                        root.dirty = true;
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Admin chat
                                    Column {
                                        width: parent.width
                                        spacing: 4
                                        Text {
                                            text: s("Admin chat", "Admin chat")
                                            font.pixelSize: 12
                                            color: root.pal.muted
                                        }
                                        Rectangle {
                                            width: parent.width
                                            height: 28
                                            radius: 6
                                            color: root.pal.windowBg
                                            border.color: teleAdminInput.activeFocus ? root.pal.accent : root.pal.border
                                            border.width: 1
                                            TextInput {
                                                id: teleAdminInput
                                                anchors.fill: parent
                                                anchors.margins: 6
                                                color: root.pal.text
                                                font.pixelSize: 12
                                                text: root.draft.tele_admin || ""
                                                onTextChanged: {
                                                    if (root.draft.tele_admin !== text) {
                                                        root.draft.tele_admin = text;
                                                        root.dirty = true;
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Token field
                                    Column {
                                        width: parent.width
                                        spacing: 4
                                        Text {
                                            text: s("Token bot Telegram", "Telegram bot token")
                                            font.pixelSize: 12
                                            color: root.pal.muted
                                        }
                                        Rectangle {
                                            width: parent.width
                                            height: 28
                                            radius: 6
                                            color: root.pal.windowBg
                                            border.color: tokenField.activeFocus ? root.pal.accent : root.pal.border
                                            border.width: 1
                                            TextInput {
                                                id: tokenField
                                                anchors.fill: parent
                                                anchors.margins: 6
                                                color: root.pal.text
                                                font.pixelSize: 12
                                                echoMode: TextInput.Password
                                                text: root.tokenInput
                                                onTextChanged: root.tokenInput = text
                                            }
                                        }
                                        Text {
                                            text: s("Chỉ ghi, không hiển thị lại", "Write-only; never shown again")
                                            font.pixelSize: 11
                                            color: root.pal.muted
                                        }
                                        Text {
                                            text: s("Token được lưu trong Windows keyring; không bao giờ trả về UI.", "Token is stored in the Windows keyring and never returned to the UI.")
                                            font.pixelSize: 11
                                            color: root.pal.muted
                                            wrapMode: Text.WordWrap
                                            width: parent.width
                                        }
                                    }

                                    // Token buttons
                                    Row {
                                        spacing: 8
                                        Rectangle {
                                            width: saveTokenText.width + 16
                                            height: 24
                                            radius: 6
                                            color: root.pal.accent
                                            opacity: (root.tokenInput.trim() !== "" && root.keyringAvailable) ? 1.0 : 0.45
                                            Text {
                                                id: saveTokenText
                                                text: s("Lưu token", "Save token")
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#ffffff"
                                                anchors.centerIn: parent
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: (root.tokenInput.trim() !== "" && root.keyringAvailable) ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                enabled: root.tokenInput.trim() !== "" && root.keyringAvailable && !root.busy
                                                onClicked: root.saveToken()
                                            }
                                        }
                                        Rectangle {
                                            width: clearTokenText.width + 16
                                            height: 24
                                            radius: 6
                                            color: "transparent"
                                            border.color: "#e5484d"
                                            border.width: 1
                                            opacity: root.tokenConfigured ? 1.0 : 0.45
                                            Text {
                                                id: clearTokenText
                                                text: s("Xóa token", "Clear token")
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#e5484d"
                                                anchors.centerIn: parent
                                            }
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: root.tokenConfigured ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                enabled: root.tokenConfigured && !root.busy
                                                onClicked: root.clearToken()
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Empty editor state
                        Text {
                            visible: root.selectedName === ""
                            width: parent.width
                            text: s("Chọn một profile để chỉnh sửa", "Select a profile to edit")
                            font.pixelSize: 14
                            color: root.pal.muted
                            horizontalAlignment: Text.AlignHCenter
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
}
