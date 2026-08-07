// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Dashboard"
    color: "transparent"

    // ── Palette ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    // ── Design constants (theme-neutral) ──
    readonly property color danger: "#e5534b"
    readonly property color amber: "#e5a63d"
    readonly property color violet: "#a78bfa"
    readonly property color blue: "#4f9cf7"
    readonly property color okGreen: pal.accent

    // ── i18n helper ──
    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    // ── Data + logic (TEST HOOKS) ──
    property var overview: ({})
    property string errorText: ""
    property string busyName: ""
    readonly property int refreshInterval: 2500

    property var profileRows: (overview && overview.profiles) || []
    property var serviceRows: (overview && overview.services) || []
    property var logLines: (overview && overview.logs && overview.logs.lines) || []
    property int pendingTotal: (overview && overview.orders) ? (overview.orders.total || 0) : 0
    property int servicesRunning: countRunning(serviceRows)
    property int runningCount: countRunning(profileRows)
    property int profileTotal: profileRows.length
    property string healthStatus: (overview && overview.health && overview.health.status) || ""
    property string handshakeApp: (overview && overview.handshake && overview.handshake.app) || "oak-core"
    property string handshakeVersion: (overview && overview.handshake && overview.handshake.version) || "—"
    property string uptimeText: (overview && overview.health && overview.health.uptime) || ""

    // ── Derived test helpers ──
    readonly property bool hasProfiles: profileRows.length > 0

    function countRunning(rows) {
        var n = 0;
        for (var i = 0; i < rows.length; i++) { if (rows[i].status === "running") n++; }
        return n;
    }

    function terminalName(path) {
        if (!path) return "MT5";
        return String(path).split(/[\\/]/).pop();
    }

    function refreshNow() {
        var r = DashApi.overview();
        if (r && r.ok === true) {
            overview = r;
            errorText = (r.warnings && r.warnings.length > 0) ? r.warnings.join("; ") : "";
        } else if (r && r.warnings && r.warnings.length > 0) {
            overview = r;
            errorText = r.warnings.join("; ");
        } else {
            errorText = (r && r.error) ? r.error : "Lỗi tải dữ liệu";
        }
    }

    function toggleProfile(name) {
        if (busyName !== "") return;
        var row = null;
        for (var i = 0; i < profileRows.length; i++) {
            if (profileRows[i].profile_name === name) { row = profileRows[i]; break; }
        }
        var running = row ? (row.status === "running") : false;
        busyName = name;
        var res = running ? Api.stop_profile(name) : Api.start_profile(name);
        busyName = "";
        if (res && res.ok === true) {
            errorText = "";
            refreshNow();
        } else {
            errorText = (res && res.error) ? res.error : "Lỗi khi đổi trạng thái profile";
        }
    }

    // ── Auto-refresh ──
    Timer {
        interval: root.refreshInterval
        repeat: true
        running: true
        onTriggered: root.refreshNow()
    }

    Component.onCompleted: root.refreshNow()

    // ════════════════════════════════════════════════════════════════
    // LAYOUT (top → bottom, no ScrollView, fits 780px window)
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
                    text: root.s("TRẠNG THÁI VẬN HÀNH", "OPERATIONS OVERVIEW")
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 2
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Bảng điều khiển", "Dashboard")
                    font.pixelSize: 22
                    font.bold: true
                    color: root.pal.text
                }
            }
            Rectangle {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 100
                height: 32
                radius: 14
                color: root.pal.accent
                visible: root.busyName === ""
                Text {
                    text: root.s("Làm mới", "Refresh")
                    font.pixelSize: 12
                    font.bold: true
                    color: "#ffffff"
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.refreshNow()
                }
            }
            Rectangle {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 100
                height: 32
                radius: 14
                color: root.pal.accent
                visible: root.busyName !== ""
                Text {
                    text: "…"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#ffffff"
                    anchors.centerIn: parent
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
                    width: badgeText.implicitWidth + 16
                    height: 20
                    radius: 4
                    color: Qt.rgba(root.danger.r, root.danger.g, root.danger.b, 0.15)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        id: badgeText
                        text: "ERROR"
                        font.pixelSize: 10
                        font.bold: true
                        font.letterSpacing: 1
                        color: root.danger
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

        // ── 3. Two-panel row ──
        Item {
            width: parent.width
            height: 340
            Row {
                anchors.fill: parent
                spacing: 12

                // ── Panel A: Profiles ──
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    clip: true
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        // Panel header
                        Row {
                            width: parent.width
                            Text {
                                text: root.s("Hồ sơ", "Profiles")
                                font.pixelSize: 15
                                font.bold: true
                                color: root.pal.text
                            }
                            Item { width: 8; height: 1 }
                            Text {
                                text: root.runningCount + "/" + root.profileTotal + (root.s(" đang chạy", " running"))
                                font.pixelSize: 11
                                color: root.pal.muted
                                font.family: "Consolas"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // Profiles list wrapper
                        Item {
                            width: parent.width
                            height: parent.height - 40

                            // Empty state
                            Text {
                                anchors.centerIn: parent
                                objectName: "profilesEmptyText"
                                text: root.s("Chưa có hồ sơ. Mở tab Hồ sơ để thêm MT5 profile.", "No profiles configured. Open Profiles to add an MT5 profile.")
                                font.pixelSize: 12
                                color: root.pal.muted
                                visible: root.profileRows.length === 0
                            }

                            // Profiles list
                            Flickable {
                                anchors.fill: parent
                                contentHeight: profileColumn.height
                                clip: true
                                visible: root.profileRows.length > 0
                                Column {
                                    id: profileColumn
                                    width: parent.width
                                    spacing: 6
                                Repeater {
                                    model: root.profileRows
                                    delegate: Item {
                                        objectName: "profileRow"
                                        width: profileColumn.width
                                        height: 52
                                        Row {
                                            anchors.fill: parent
                                            spacing: 10

                                            // Status dot
                                            Rectangle {
                                                width: 10
                                                height: 10
                                                radius: 5
                                                color: modelData.status === "running" ? root.okGreen : root.pal.muted
                                                opacity: modelData.status === "running" ? 1.0 : 0.35
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            // Name + terminal
                                            Column {
                                                width: parent.width - 164
                                                spacing: 2
                                                anchors.verticalCenter: parent.verticalCenter
                                                Text {
                                                    text: modelData.profile_name || ""
                                                    font.pixelSize: 13
                                                    font.bold: true
                                                    color: root.pal.text
                                                    elide: Text.ElideRight
                                                    width: parent.width
                                                }
                                                Text {
                                                    text: root.terminalName(modelData.path)
                                                    font.pixelSize: 11
                                                    color: root.pal.muted
                                                    elide: Text.ElideRight
                                                    width: parent.width
                                                }
                                            }

                                            // State text
                                            Text {
                                                text: modelData.status === "running" ? root.s("ĐANG CHẠY", "RUNNING") : root.s("NHÀN", "IDLE")
                                                font.pixelSize: 11
                                                font.family: "Consolas"
                                                width: 60
                                                elide: Text.ElideRight
                                                color: modelData.status === "running" ? root.okGreen : root.pal.muted
                                                anchors.verticalCenter: parent.verticalCenter
                                            }

                                            // Start/Stop button
                                            Rectangle {
                                                objectName: "profileToggleBtn"
                                                width: 64
                                                height: 26
                                                radius: 8
                                                color: modelData.status === "running" ? "transparent" : root.pal.accent
                                                border.color: modelData.status === "running" ? root.pal.border : root.pal.accent
                                                border.width: 1
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: root.busyName !== modelData.profile_name
                                                Text {
                                                    text: modelData.status === "running" ? root.s("Dừng", "Stop") : root.s("Chạy", "Start")
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    color: modelData.status === "running" ? root.danger : "#ffffff"
                                                    anchors.centerIn: parent
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: root.toggleProfile(modelData.profile_name)
                                                }
                                            }
                                            // Busy indicator
                                            Rectangle {
                                                width: 64
                                                height: 26
                                                radius: 8
                                                color: root.pal.surface
                                                border.color: root.pal.border
                                                border.width: 1
                                                anchors.verticalCenter: parent.verticalCenter
                                                visible: root.busyName === modelData.profile_name
                                                Text {
                                                    text: "…"
                                                    font.pixelSize: 11
                                                    font.bold: true
                                                    color: root.pal.muted
                                                    anchors.centerIn: parent
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

                // ── Panel B: Live Console ──
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    clip: true
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        // Panel header
                        Row {
                            width: parent.width
                            Text {
                                text: root.s("Nhật ký trực tiếp", "Live Console")
                                font.pixelSize: 15
                                font.bold: true
                                color: root.pal.text
                            }
                            Item { width: 8; height: 1 }
                            Rectangle {
                                width: healthBadge.implicitWidth + 16
                                height: 22
                                radius: 8
                                color: root.healthStatus === "ok" ? Qt.rgba(root.okGreen.r, root.okGreen.g, root.okGreen.b, 0.15) : Qt.rgba(root.pal.muted.r, root.pal.muted.g, root.pal.muted.b, 0.15)
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    id: healthBadge
                                    text: root.healthStatus !== "" ? root.healthStatus : "—"
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: root.healthStatus === "ok" ? root.okGreen : root.pal.muted
                                    anchors.centerIn: parent
                                }
                            }
                        }

                        // Log content
                        Item {
                            width: parent.width
                            height: parent.height - 80
                            // Empty state
                            Text {
                                anchors.centerIn: parent
                                text: root.s("Chưa có dòng nhật ký.", "No log lines yet.")
                                font.pixelSize: 12
                                color: root.pal.muted
                                visible: root.logLines.length === 0
                            }
                            // Log view
                            Flickable {
                                id: logFlickable
                                anchors.fill: parent
                                contentHeight: logText.height
                                clip: true
                                visible: root.logLines.length > 0
                                TextEdit {
                                    id: logText
                                    width: logFlickable.width
                                    readOnly: true
                                    selectByMouse: true
                                    text: root.logLines.join("\n")
                                    font.family: "Consolas"
                                    font.pixelSize: 12
                                    color: root.pal.muted
                                    wrapMode: TextEdit.NoWrap
                                }
                                ScrollBar.vertical: ScrollBar {
                                    policy: ScrollBar.AsNeeded
                                }
                            }
                        }

                        // Meta row
                        Row {
                            width: parent.width
                            spacing: 6
                            Text {
                                text: root.handshakeApp
                                font.pixelSize: 11
                                color: root.pal.muted
                            }
                            Text {
                                text: "v" + root.handshakeVersion
                                font.pixelSize: 11
                                color: root.pal.muted
                            }
                            Item { width: parent.width - 200; height: 1 }
                            Text {
                                text: root.s("Dữ liệu qua sidecar", "Data via sidecar")
                                font.pixelSize: 11
                                color: root.pal.muted
                            }
                        }
                    }
                }
            }
        }

        // ── 4. Metrics row ──
        Item {
            width: parent.width
            height: 84
            Row {
                anchors.fill: parent
                spacing: 12

                // Tile 1: Log lines (amber)
                Rectangle {
                    width: (parent.width - 36) / 4
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: root.s("Dòng nhật ký", "Log lines")
                            font.pixelSize: 11
                            color: root.pal.muted
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: String(root.logLines.length)
                            font.pixelSize: 22
                            font.bold: true
                            font.family: "Consolas"
                            color: root.amber
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }

                // Tile 2: Pending tasks (violet)
                Rectangle {
                    width: (parent.width - 36) / 4
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: root.s("Lệnh chờ", "Pending tasks")
                            font.pixelSize: 11
                            color: root.pal.muted
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: String(root.pendingTotal)
                            font.pixelSize: 22
                            font.bold: true
                            font.family: "Consolas"
                            color: root.violet
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }

                // Tile 3: Services running (okGreen)
                Rectangle {
                    width: (parent.width - 36) / 4
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: root.s("Dịch vụ chạy", "Services running")
                            font.pixelSize: 11
                            color: root.pal.muted
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: String(root.servicesRunning)
                            font.pixelSize: 22
                            font.bold: true
                            font.family: "Consolas"
                            color: root.okGreen
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }

                // Tile 4: Connection (okGreen or blue)
                Rectangle {
                    width: (parent.width - 36) / 4
                    height: parent.height
                    radius: 14
                    color: root.pal.surface
                    border.color: root.pal.border
                    border.width: 1
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: root.s("Kết nối", "Connection")
                            font.pixelSize: 11
                            color: root.pal.muted
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                        Text {
                            text: root.healthStatus !== "" ? root.healthStatus : "—"
                            font.pixelSize: 22
                            font.bold: true
                            font.family: "Consolas"
                            color: root.healthStatus === "ok" ? root.okGreen : root.blue
                            anchors.horizontalCenter: parent.horizontalCenter
                        }
                    }
                }
            }
        }
    }
}
