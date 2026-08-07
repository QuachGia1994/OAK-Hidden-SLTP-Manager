// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Signals"
    color: "transparent"
    anchors.fill: parent

    readonly property var pal: DesignTokens.palette(Theme.currentTheme)
    readonly property color okGreen: root.pal.accent
    property var services: []
    property var profileNames: []
    property string selectedProfile: ""
    property string busyKey: ""
    property string confirmKey: ""
    property bool busyLoading: false
    property string errorText: ""
    property string noticeText: ""
    property string runningServices: ""
    property var logLines: []

    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    function serviceLogs(key) {
        var prefix = "[svc:" + key + "]";
        var result = [];
        for (var i = logLines.length - 1; i >= 0 && result.length < 5; i--) {
            if (String(logLines[i]).indexOf(prefix) === 0) {
                result.unshift(logLines[i]);
            }
        }
        return result;
    }

    function runningCount() {
        var n = 0;
        for (var i = 0; i < services.length; i++) {
            if (services[i].status === "running") n++;
        }
        return n;
    }

    function refreshNow() {
        busyLoading = true;
        var svc = ShellApi.services();
        if (svc.ok) {
            services = svc.result;
        } else {
            errorText = svc.error || "";
        }
        var logs = ShellApi.logs_tail(200, "", "ALL");
        if (logs.ok) {
            logLines = logs.result.lines || [];
        }
        var plist = Api.list_profiles();
        if (plist && plist.length > 0) {
            profileNames = plist.map(function(p) { return p.profile_name; });
            if (selectedProfile === "" && profileNames.length > 0) {
                selectedProfile = profileNames[0];
            }
        }
        runningServices = runningCount() + "/" + services.length;
        busyLoading = false;
    }

    function startService(key) {
        if (busyKey !== "") return;
        var svc = serviceByKey(key);
        if (svc === null) return;
        if (svc.kind === "on_demand") {
            noticeText = s("Dịch vụ chạy theo yêu cầu — dùng tab Bộ lọc CP.", "On-demand service — use the VN30 Advisor tab.");
            return;
        }
        if (svc.trading_risk === "critical") {
            confirmKey = key;
            noticeText = s("Nhấn lần nữa để xác nhận khởi động.", "Press again to confirm start.");
            return;
        }
        doStart(key, false);
    }

    function doStart(key, confirm) {
        busyKey = key;
        var r = ShellApi.service_start(key, selectedProfile, confirm);
        busyKey = "";
        if (!r.ok) {
            errorText = r.error || "";
        } else {
            var res = r.result;
            if (res.started === true) {
                noticeText = s("Đã khởi động.", "Started.");
                confirmKey = "";
            } else if (res.reason === "confirmation_required") {
                confirmKey = key;
                noticeText = s("Nhấn lần nữa để xác nhận khởi động.", "Press again to confirm start.");
            } else if (res.reason === "on_demand_service") {
                noticeText = s("Dịch vụ chạy theo yêu cầu — dùng tab Bộ lọc CP.", "On-demand service — use the VN30 Advisor tab.");
            } else if (res.reason === "not_configured") {
                noticeText = res.detail || s("Chưa cấu hình.", "Not configured.");
            } else if (res.reason === "already_running" || res.reason === "already_running_lock") {
                noticeText = s("Đang chạy rồi.", "Already running.");
            } else if (res.reason === "unknown_service") {
                noticeText = s("Dịch vụ không xác định.", "Unknown service.");
            } else if (res.reason === "spawn_failed" || res.reason === "not_supported_in_frozen") {
                errorText = res.detail || res.reason || "";
            } else {
                noticeText = res.reason || "";
            }
        }
        refreshNow();
    }

    function stopService(key) {
        busyKey = key;
        var r = ShellApi.service_stop(key);
        busyKey = "";
        if (!r.ok) {
            errorText = r.error || "";
        } else if (r.result.stopped === true) {
            noticeText = s("Đã dừng.", "Stopped.");
        } else {
            noticeText = r.result.reason || "";
        }
        refreshNow();
    }

    function selectProfile(name) {
        selectedProfile = name;
    }

    function serviceByKey(key) {
        for (var i = 0; i < services.length; i++) {
            if (services[i].key === key) return services[i];
        }
        return null;
    }

    // ── Confirm expiry Timer ──
    Timer {
        id: confirmTimer
        interval: 8000
        running: confirmKey !== ""
        repeat: false
        onTriggered: confirmKey = ""
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
                    text: root.s("DỊCH VỤ VẬN HÀNH", "SERVICES")
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Tín hiệu", "Signals")
                    font.pixelSize: 20
                    font.bold: true
                    color: root.pal.text
                }
            }
            Item { width: parent.width - 200; height: 1 }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Text {
                    text: root.runningServices
                    color: root.pal.muted
                    font.pixelSize: 12
                    anchors.verticalCenter: parent.verticalCenter
                }
                Rectangle {
                    width: 90
                    height: 28
                    radius: 8
                    color: "transparent"
                    border.color: root.pal.border
                    border.width: 1
                    objectName: "svcRefreshBtn"
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
            visible: root.profileNames.length > 1 || root.selectedProfile !== ""
            spacing: 8
            Text {
                text: root.s("Hồ sơ cho dịch vụ audit", "Profile for audit service")
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
                    objectName: "svcProfileChip"
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

        // ── Services grid ──
        Flickable {
            width: parent.width
            height: parent.height - 44 - (root.errorText !== "" ? 46 : 0) - (root.noticeText !== "" ? 46 : 0) - (root.profileNames.length > 1 || root.selectedProfile !== "" ? 34 : 0) - 16
            contentHeight: serviceGrid.height
            clip: true

            Grid {
                id: serviceGrid
                columns: 2
                spacing: 12
                width: parent.width

                Repeater {
                    model: root.services

                    Rectangle {
                        width: (serviceGrid.width - 12) / 2
                        height: 240
                        color: root.pal.surface
                        border.color: root.pal.border
                        border.width: 1
                        radius: 8
                        objectName: "serviceCard"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 6

                            // Row 1: status dot + label + status badge
                            Row {
                                width: parent.width
                                spacing: 8
                                Rectangle {
                                    width: 10
                                    height: 10
                                    radius: 5
                                    color: modelData.status === "running" ? root.okGreen
                                        : (modelData.status === "exited" || modelData.status === "crashed") ? "#e5484d"
                                        : root.pal.muted
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: modelData.label || modelData.key
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: root.pal.text
                                    elide: Text.ElideRight
                                    width: parent.width - 12 - 80
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Item { width: 1; height: 1 }
                                Text {
                                    text: modelData.status === "running" ? root.s("Đang chạy", "Running")
                                        : modelData.status === "stopped" ? root.s("Dừng", "Stopped")
                                        : modelData.status === "exited" ? root.s("Đã thoát", "Exited")
                                        : modelData.status === "crashed" ? root.s("Lỗi", "Crashed")
                                        : modelData.status
                                    font.pixelSize: 11
                                    color: modelData.status === "running" ? root.okGreen
                                        : (modelData.status === "exited" || modelData.status === "crashed") ? "#e5484d"
                                        : root.pal.muted
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            // Row 2: key + scope
                            Row {
                                spacing: 8
                                Text {
                                    text: modelData.key
                                    font.pixelSize: 11
                                    font.family: "monospace"
                                    color: root.pal.muted
                                }
                                Rectangle {
                                    width: scopeText.implicitWidth + 10
                                    height: 18
                                    radius: 4
                                    color: "transparent"
                                    border.color: root.pal.border
                                    border.width: 1
                                    Text {
                                        id: scopeText
                                        text: modelData.scope || ""
                                        font.pixelSize: 10
                                        color: root.pal.muted
                                        anchors.centerIn: parent
                                    }
                                }
                            }

                            // Row 3: risk badge + execution warning
                            Row {
                                spacing: 6
                                visible: modelData.trading_risk === "critical" || modelData.execution_armed === true
                                Rectangle {
                                    visible: modelData.trading_risk === "critical"
                                    width: riskBadge.implicitWidth + 12
                                    height: 18
                                    radius: 4
                                    color: "transparent"
                                    border.color: "#e5484d"
                                    border.width: 1
                                    objectName: "riskBadge"
                                    Text {
                                        id: riskBadge
                                        text: root.s("RỦI RO CAO", "HIGH RISK")
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: "#e5484d"
                                        anchors.centerIn: parent
                                    }
                                }
                                Text {
                                    visible: modelData.execution_armed === true
                                    text: root.s("⚠ Thực thi tín hiệu đang BẬT", "⚠ Signal execution is ON")
                                    font.pixelSize: 11
                                    color: "#e5484d"
                                    objectName: "execWarning"
                                }
                            }

                            // Meta text
                            Text {
                                text: modelData.status === "running" && modelData.pid
                                    ? root.s("PID ", "PID ") + modelData.pid
                                    : (modelData.exit_code !== null && modelData.exit_code !== undefined)
                                    ? root.s("Mã thoát ", "Exit code ") + modelData.exit_code
                                    : (!modelData.configured && modelData.config_note)
                                    ? modelData.config_note
                                    : (modelData.note || "")
                                font.pixelSize: 11
                                color: (!modelData.configured && modelData.config_note) ? "#e5484d" : root.pal.muted
                                elide: Text.ElideRight
                                width: parent.width
                                objectName: "serviceMeta"
                            }

                            // Log preview
                            Rectangle {
                                width: parent.width
                                height: 78
                                color: Qt.rgba(root.pal.windowBg.r, root.pal.windowBg.g, root.pal.windowBg.b, 0.6)
                                border.color: root.pal.border
                                border.width: 1
                                radius: 6
                                clip: true

                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    font.pixelSize: 11
                                    font.family: "monospace"
                                    wrapMode: Text.Wrap
                                    elide: Text.ElideNone
                                    text: root.serviceLogs(modelData.key).length > 0
                                        ? root.serviceLogs(modelData.key).join("\n")
                                        : root.s("— không có nhật ký —", "— no logs —")
                                    color: root.serviceLogs(modelData.key).length > 0 ? root.pal.muted : root.pal.muted
                                    objectName: "serviceLog"
                                }
                            }

                            // Button row
                            Row {
                                width: parent.width
                                spacing: 6

                                // On-demand note
                                Text {
                                    visible: modelData.kind === "on_demand"
                                    text: modelData.note || ""
                                    font.pixelSize: 11
                                    color: root.pal.muted
                                    objectName: "onDemandNote"
                                }

                                // Start/Stop/Confirm button
                                Rectangle {
                                    visible: modelData.kind !== "on_demand"
                                    width: Math.max(90, btnText.implicitWidth + 20)
                                    height: 28
                                    radius: 6
                                    color: modelData.status === "running"
                                        ? "transparent"
                                        : root.confirmKey === modelData.key
                                        ? "#e5484d"
                                        : root.pal.accent
                                    border.color: modelData.status === "running"
                                        ? root.pal.border
                                        : root.confirmKey === modelData.key
                                        ? "#e5484d"
                                        : root.pal.accent
                                    border.width: 1
                                    opacity: root.busyKey === modelData.key ? 0.5 : 1.0
                                    objectName: "serviceToggleBtn"

                                    Text {
                                        id: btnText
                                        text: root.busyKey === modelData.key
                                            ? (modelData.status === "running" ? root.s("Dừng…", "Stop…") : root.s("Chạy…", "Start…"))
                                            : modelData.status === "running"
                                            ? root.s("Dừng", "Stop")
                                            : root.confirmKey === modelData.key
                                            ? root.s("Xác nhận khởi động?", "Confirm start?")
                                            : root.s("Chạy", "Start")
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: modelData.status === "running" ? "#e5484d" : "#ffffff"
                                        anchors.centerIn: parent
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: root.busyKey !== modelData.key
                                        onClicked: {
                                            if (modelData.status === "running") {
                                                root.stopService(modelData.key);
                                            } else if (root.confirmKey === modelData.key) {
                                                root.doStart(modelData.key, true);
                                            } else {
                                                root.startService(modelData.key);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
