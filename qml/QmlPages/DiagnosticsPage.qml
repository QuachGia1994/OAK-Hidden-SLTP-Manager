// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Diagnostics"
    color: "transparent"
    anchors.fill: parent

    // ── Palette ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    // ── Error tone (theme-neutral) ──
    readonly property color danger: "#e5534b"

    // ── i18n helper ──
    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    // ── Data + logic (TEST HOOKS) ──
    property var runtime: ({})
    property var logResult: ({})
    property var logLines: (logResult && logResult.lines) || []
    property string query: ""
    property string level: "ALL"
    property bool displayCleared: false
    property string errorText: ""
    property string notice: ""
    property string exportLocation: ""
    property bool busy: false

    // ── Derived ──
    property int visibleCount: displayCleared ? 0 : (logLines.length)
    property string latestLog: (runtime && runtime.latest_log) || "\u2014"
    property string runtimeRoot: (runtime && runtime.root_name) || "\u2014"
    property string pyVersion: (runtime && runtime.python) || "\u2014"
    property string modeText: (runtime && runtime.mode) || "\u2014"
    property int profileCount: (runtime && runtime.profiles) || 0
    property bool settingsFile: !!(runtime && runtime.settings)

    // ── Functions ──
    function refreshNow() {
        busy = true;
        var d = ShellApi.diagnostics();
        if (d && d.ok) {
            runtime = d.result;
        } else {
            errorText = (d && d.error) ? d.error : s("Lỗi tải chẩn đoán", "Diagnostics load failed");
        }
        var t = ShellApi.logs_tail(400, query, level);
        if (t && t.ok) {
            logResult = t.result;
            errorText = "";
        } else {
            errorText = (t && t.error) ? t.error : errorText;
        }
        displayCleared = false;
        busy = false;
    }

    function setQuery(q) {
        query = q;
        refreshNow();
    }

    function setLevel(l) {
        level = l;
        refreshNow();
    }

    function exportBundle() {
        if (busy) return;
        busy = true;
        var r = ShellApi.export_bundle();
        if (r && r.ok && r.result) {
            exportLocation = r.result.path || r.result.directory || "";
            notice = s("Đã xuất ", "Exported ") + (r.result.file_name || "") + s(" ra đĩa.", " to disk.");
        } else {
            notice = (r && r.error) ? r.error : s("Xuất gói thất bại", "Export failed");
        }
        busy = false;
    }

    function clearDisplay() {
        displayCleared = true;
        notice = s("Đã xóa vùng hiển thị; file log không bị thay đổi.", "Display cleared; log files unchanged.");
    }

    function copyReport() {
        try {
            var lines = [
                "# OAK diagnostic report",
                "mode: " + modeText,
                "python: " + pyVersion,
                "root: " + runtimeRoot,
                "profiles: " + String(profileCount),
                "settings: " + (settingsFile ? "yes" : "no"),
                "latest log: " + latestLog,
                "filter query: " + query,
                "filter level: " + level,
                "visible lines: " + String(visibleCount),
                ""
            ];
            if (!displayCleared) {
                for (var i = 0; i < logLines.length; i++) {
                    lines.push(logLines[i]);
                }
            }
            Qt.clipboard.setText(lines.join("\n"));
            notice = s("Đã sao chép báo cáo.", "Report copied.");
        } catch (e) {
            notice = s("Sao chép báo cáo thất bại.", "Report copy failed.");
        }
    }

    function copyLog() {
        try {
            Qt.clipboard.setText(displayCleared ? "" : logLines.join("\n"));
            notice = s("Đã sao chép log đang lọc.", "Filtered log copied.");
        } catch (e) {
            notice = s("Sao chép log thất bại.", "Log copy failed.");
        }
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
                    text: root.s("TRẠNG THÁI SIDECAR", "SIDECAR STATUS")
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 2
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Chẩn đoán", "Diagnostics")
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
                visible: !root.busy
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
                visible: root.busy
                Text {
                    text: "\u2026"
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

        // ── 3. Notice line ──
        Text {
            width: parent.width
            height: root.notice !== "" ? 18 : 0
            visible: root.notice !== ""
            text: root.notice
            font.pixelSize: 12
            color: root.pal.muted
        }

        // ── 4. Runtime panel ──
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
                spacing: 8
                Text {
                    text: root.s("Kiểm tra runtime", "Runtime check")
                    font.pixelSize: 15
                    font.bold: true
                    color: root.pal.text
                }
                Row {
                    spacing: 16
                    Column {
                        spacing: 2
                        Text { text: root.s("Chế độ", "Mode"); font.pixelSize: 11; color: root.pal.muted }
                        Text { text: root.modeText; font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                    Column {
                        spacing: 2
                        Text { text: "Python"; font.pixelSize: 11; color: root.pal.muted }
                        Text { text: root.pyVersion; font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                    Column {
                        spacing: 2
                        Text { text: "Root"; font.pixelSize: 11; color: root.pal.muted }
                        Text { text: root.runtimeRoot; font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                    Column {
                        spacing: 2
                        Text { text: root.s("Hồ sơ", "Profiles"); font.pixelSize: 11; color: root.pal.muted }
                        Text { text: String(root.profileCount); font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                    Column {
                        spacing: 2
                        Text { text: root.s("Cài đặt", "Settings"); font.pixelSize: 11; color: root.pal.muted }
                        Text { text: root.settingsFile ? "✓" : "\u2717"; font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                    Column {
                        spacing: 2
                        Text { text: root.s("Log mới nhất", "Latest log"); font.pixelSize: 11; color: root.pal.muted }
                        Text { text: root.latestLog; font.pixelSize: 13; font.bold: true; font.family: "Consolas"; color: root.pal.text }
                    }
                }
                Text {
                    text: root.s("Chẩn đoán mặc định không chứa secrets.", "Diagnostics are redacted by default.")
                    font.pixelSize: 11
                    font.family: "Consolas"
                    color: root.pal.muted
                }
            }
        }

        // ── 5. Log panel ──
        Rectangle {
            width: parent.width
            height: parent.height - 280
            radius: 14
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            clip: true
            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8

                // Header Row
                Row {
                    width: parent.width
                    Text {
                        text: root.s("Nhật ký", "Log")
                        font.pixelSize: 15
                        font.bold: true
                        color: root.pal.text
                    }
                    Item { width: 8; height: 1 }
                    Text {
                        text: String(root.visibleCount) + "/" + (root.logResult.requested ? String(root.logResult.requested) : "0")
                        font.pixelSize: 11
                        font.family: "Consolas"
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Item { width: parent.width - 200; height: 1 }
                }

                // Actions Row
                Row {
                    spacing: 8
                    Rectangle {
                        width: copyReportLabel.implicitWidth + 20
                        height: 28
                        radius: 8
                        color: "transparent"
                        border.color: root.pal.border
                        border.width: 1
                        Text {
                            id: copyReportLabel
                            text: root.s("Sao chép báo cáo", "Copy report")
                            font.pixelSize: 11
                            font.bold: true
                            color: root.pal.text
                            anchors.centerIn: parent
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.copyReport()
                        }
                    }
                    Rectangle {
                        width: copyLogLabel.implicitWidth + 20
                        height: 28
                        radius: 8
                        color: "transparent"
                        border.color: root.pal.border
                        border.width: 1
                        Text {
                            id: copyLogLabel
                            text: root.s("Sao chép log", "Copy log")
                            font.pixelSize: 11
                            font.bold: true
                            color: root.pal.text
                            anchors.centerIn: parent
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.copyLog()
                        }
                    }
                    Rectangle {
                        width: exportLabel.implicitWidth + 20
                        height: 28
                        radius: 8
                        color: "transparent"
                        border.color: root.pal.border
                        border.width: 1
                        Text {
                            id: exportLabel
                            text: root.s("Xuất gói", "Export bundle")
                            font.pixelSize: 11
                            font.bold: true
                            color: root.pal.text
                            anchors.centerIn: parent
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.exportBundle()
                        }
                    }
                    Rectangle {
                        width: clearLabel.implicitWidth + 20
                        height: 28
                        radius: 8
                        color: "transparent"
                        border.color: root.pal.border
                        border.width: 1
                        Text {
                            id: clearLabel
                            text: root.s("Xóa hiển thị", "Clear display")
                            font.pixelSize: 11
                            font.bold: true
                            color: root.pal.text
                            anchors.centerIn: parent
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.clearDisplay()
                        }
                    }
                }

                // Filters Row
                Row {
                    spacing: 8
                    TextField {
                        id: searchField
                        width: 320
                        font.pixelSize: 12
                        placeholderText: root.s("Tìm log: profile, ERROR\u2026", "Search logs: profile, ERROR\u2026")
                        onTextChanged: root.setQuery(text)
                    }
                    ComboBox {
                        id: levelCombo
                        width: 110
                        model: ["ALL", "INFO", "WARN", "ERROR"]
                        currentIndex: {
                            if (root.level === "ERROR") return 3;
                            if (root.level === "WARN") return 2;
                            if (root.level === "INFO") return 1;
                            return 0;
                        }
                        onActivated: root.setLevel(currentText)
                    }
                }

                // Export location
                Text {
                    width: parent.width
                    height: root.exportLocation !== "" ? 16 : 0
                    visible: root.exportLocation !== ""
                    text: root.s("Đã xuất tới: ", "Exported to: ") + root.exportLocation
                    font.pixelSize: 11
                    font.family: "Consolas"
                    color: root.pal.muted
                }

                // Log area
                Item {
                    width: parent.width
                    height: parent.height - 130
                    Text {
                        anchors.centerIn: parent
                        text: root.s("Chưa có dòng nhật ký phù hợp.", "No matching log lines.")
                        font.pixelSize: 12
                        color: root.pal.muted
                        visible: root.visibleCount === 0
                    }
                    Flickable {
                        anchors.fill: parent
                        contentHeight: logText.height
                        clip: true
                        visible: root.visibleCount > 0
                        TextEdit {
                            id: logText
                            width: parent.width
                            readOnly: true
                            selectByMouse: true
                            text: root.displayCleared ? "" : root.logLines.join("\n")
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
            }
        }
    }
}
