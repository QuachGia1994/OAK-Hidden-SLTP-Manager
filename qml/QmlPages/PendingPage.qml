// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_Pending"
    color: "transparent"
    anchors.fill: parent

    readonly property var pal: DesignTokens.palette(Theme.currentTheme)
    readonly property color okGreen: root.pal.accent
    property var profileNames: []
    property string selectedProfile: ""
    property var pendingData: null
    property bool busyLoading: false
    property string errorText: ""
    property string noticeText: ""
    property string deleteConfirmId: ""

    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    function refreshNow() {
        busyLoading = true;
        var plist = Api.list_profiles();
        profileNames = (plist && plist.length) ? plist.map(function(p) { return p.profile_name; }) : [];
        if (selectedProfile === "" && profileNames.length > 0) {
            selectedProfile = profileNames[0];
        }
        if (selectedProfile === "") {
            noticeText = s("Chưa có hồ sơ nào.", "No profiles yet.");
            pendingData = null;
            busyLoading = false;
            return;
        }
        var r = ShellApi.pending(selectedProfile);
        pendingData = r.ok ? r.result : null;
        if (!r.ok) {
            errorText = r.error || "";
        }
        busyLoading = false;
    }

    function selectProfile(name) {
        selectedProfile = name;
        deleteConfirmId = "";
        refreshNow();
    }

    function deleteItem(id) {
        if (deleteConfirmId === id) {
            var r = ShellApi.pending_delete(selectedProfile, id);
            deleteConfirmId = "";
            noticeText = (r.ok && r.result.deleted) ? s("Đã xóa tác vụ.", "Item deleted.") : s("Không tìm thấy tác vụ.", "Item not found.");
            refreshNow();
        } else {
            deleteConfirmId = id;
        }
    }

    function clearDone() {
        var r = ShellApi.pending_clear_done(selectedProfile);
        noticeText = r.ok ? (s("Đã xóa ") + (r.result.cleared || 0) + s(" tác vụ xong.", " done items cleared.")) : (r.error || "");
        refreshNow();
    }

    function rowSummary(row) {
        if (!row) return "";
        var skip = {id: true, kind: true, status: true, file_name: true, value: true, profile: true};
        var parts = [];
        for (var k in row) {
            if (skip[k]) continue;
            var v = row[k];
            if (v === null || v === undefined) continue;
            parts.push(k + "=" + v);
        }
        var joined = parts.join(" · ");
        if (joined.length > 120) joined = joined.substring(0, 120) + "\u2026";
        if (parts.length === 0 && row.value !== null && row.value !== undefined) {
            joined = String(row.value);
        }
        return joined;
    }

    // Confirm expiry Timer
    Timer {
        interval: 8000
        running: deleteConfirmId !== ""
        repeat: false
        onTriggered: deleteConfirmId = ""
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
                    text: root.s("TÁC VỤ ĐÃ LÊN LỊCH", "SCHEDULED TASKS")
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Lệnh chờ xử lý", "Pending")
                    font.pixelSize: 20
                    font.bold: true
                    color: root.pal.text
                }
            }
            Item { width: parent.width - 400; height: 1 }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                // Profile selector inline
                Row {
                    visible: root.profileNames.length > 0
                    spacing: 6
                    Repeater {
                        model: root.profileNames
                        Rectangle {
                            width: pendingProfileChipText.implicitWidth + 16
                            height: 24
                            radius: 6
                            color: "transparent"
                            border.color: root.selectedProfile === modelData ? root.pal.accent : root.pal.border
                            border.width: 1
                            objectName: "pendingProfileChip"
                            Text {
                                id: pendingProfileChipText
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
                Rectangle {
                    width: 90
                    height: 28
                    radius: 8
                    color: "transparent"
                    border.color: root.pal.border
                    border.width: 1
                    objectName: "pendingRefreshBtn"
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
                    width: 110
                    height: 28
                    radius: 8
                    color: "transparent"
                    border.color: root.pal.border
                    border.width: 1
                    objectName: "pendingClearBtn"
                    Text {
                        text: root.s("Xóa tác vụ xong", "Clear done")
                        font.pixelSize: 12
                        color: root.pal.text
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.clearDone()
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

        // ── Summary panel ──
        Rectangle {
            width: parent.width
            height: 84
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            radius: 8

            Row {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 20

                // statTotal
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: root.pendingData ? String(root.pendingData.total || 0) : "0"
                        font.pixelSize: 20
                        font.bold: true
                        color: root.pal.text
                        objectName: "statTotal"
                    }
                    Text {
                        text: root.s("Tổng", "Total")
                        font.pixelSize: 11
                        color: root.pal.muted
                    }
                }

                // statWaiting
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: root.pendingData ? String(root.pendingData.waiting || 0) : "0"
                        font.pixelSize: 20
                        font.bold: true
                        color: root.pal.accent
                        objectName: "statWaiting"
                    }
                    Text {
                        text: root.s("Chờ", "Waiting")
                        font.pixelSize: 11
                        color: root.pal.muted
                    }
                }

                // statDone
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: root.pendingData ? String(root.pendingData.done || 0) : "0"
                        font.pixelSize: 20
                        font.bold: true
                        color: root.okGreen
                        objectName: "statDone"
                    }
                    Text {
                        text: root.s("Xong", "Done")
                        font.pixelSize: 11
                        color: root.pal.muted
                    }
                }

                // File stats
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12
                    visible: root.pendingData && root.pendingData.files && root.pendingData.files.length > 0
                    Repeater {
                        model: root.pendingData ? (root.pendingData.files || []) : []
                        Text {
                            text: modelData.name + ": " + modelData.count
                            font.pixelSize: 11
                            color: root.pal.muted
                            objectName: "pendingFileStat"
                        }
                    }
                }
            }
        }

        // ── Items panel ──
        Rectangle {
            width: parent.width
            height: parent.height - 44 - (root.errorText !== "" ? 46 : 0) - (root.noticeText !== "" ? 46 : 0) - 84 - 16
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            radius: 8
            clip: true

            Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                // Header row
                Row {
                    width: parent.width
                    spacing: 8
                    Text {
                        text: root.s("Tác vụ", "Items")
                        font.pixelSize: 13
                        font.bold: true
                        color: root.pal.text
                    }
                    Text {
                        text: root.pendingData ? String(root.pendingData.items ? root.pendingData.items.length : 0) : "0"
                        font.pixelSize: 13
                        color: root.pal.muted
                    }
                }

                // Empty state
                Text {
                    visible: !root.pendingData || !root.pendingData.items || root.pendingData.items.length === 0
                    text: root.s("Không có lệnh chờ xử lý.", "No pending items.")
                    font.pixelSize: 12
                    color: root.pal.muted
                    objectName: "pendingEmptyText"
                }

                // Items list
                Flickable {
                    width: parent.width
                    height: parent.height - 30
                    contentHeight: pendingColumn.height
                    clip: true

                    Column {
                        id: pendingColumn
                        width: parent.width
                        spacing: 4

                        Repeater {
                            model: root.pendingData ? (root.pendingData.items || []) : []
                            Row {
                                objectName: "pendingRow"
                                width: pendingColumn.width
                                height: 30
                                spacing: 8

                                // Kind badge
                                Rectangle {
                                    width: 110
                                    height: 22
                                    radius: 4
                                    color: "transparent"
                                    border.color: root.pal.border
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        text: modelData.kind === "entries" ? root.s("Lệnh chờ", "Entry")
                                            : modelData.kind === "scheduled closes" ? root.s("Đóng theo lịch", "Scheduled close")
                                            : modelData.kind === "partials" ? root.s("Chốt 1 phần", "Partial")
                                            : modelData.kind
                                        font.pixelSize: 10
                                        color: root.pal.text
                                        anchors.centerIn: parent
                                        elide: Text.ElideRight
                                        width: 104
                                        horizontalAlignment: Text.AlignHCenter
                                    }
                                }

                                // Status badge
                                Rectangle {
                                    width: statusText.implicitWidth + 12
                                    height: 22
                                    radius: 4
                                    color: "transparent"
                                    border.color: modelData.status === "waiting" ? root.pal.accent : root.okGreen
                                    border.width: 1
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        id: statusText
                                        text: modelData.status === "waiting" ? root.s("Chờ", "Waiting") : root.s("Xong", "Done")
                                        font.pixelSize: 10
                                        color: modelData.status === "waiting" ? root.pal.accent : root.okGreen
                                        anchors.centerIn: parent
                                    }
                                }

                                // Summary text
                                Text {
                                    text: root.rowSummary(modelData)
                                    font.pixelSize: 11
                                    color: root.pal.text
                                    elide: Text.ElideRight
                                    width: parent.width - 110 - 60 - 80 - 8 * 5
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                // Spacer
                                Item { width: 1; height: 1; anchors.verticalCenter: parent.verticalCenter }

                                // Copy button
                                Rectangle {
                                    width: 40
                                    height: 22
                                    radius: 4
                                    color: "transparent"
                                    border.color: root.pal.border
                                    border.width: 1
                                    objectName: "pendingCopyBtn"
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        text: "Copy"
                                        font.pixelSize: 10
                                        color: root.pal.text
                                        anchors.centerIn: parent
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            try {
                                                var summary = root.rowSummary(modelData) + " [" + modelData.id + "]";
                                                Qt.clipboard.setText(summary);
                                            } catch(e) {}
                                        }
                                    }
                                }

                                // Delete button
                                Rectangle {
                                    width: deleteConfirmId === modelData.id ? 80 : 50
                                    height: 22
                                    radius: 4
                                    color: "transparent"
                                    border.color: deleteConfirmId === modelData.id ? "#e5484d" : root.pal.border
                                    border.width: 1
                                    objectName: "pendingDeleteBtn"
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        text: root.deleteConfirmId === modelData.id ? root.s("Xác nhận?", "Confirm?") : root.s("Xóa", "Delete")
                                        font.pixelSize: 10
                                        color: root.deleteConfirmId === modelData.id ? "#e5484d" : root.pal.text
                                        anchors.centerIn: parent
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.deleteItem(modelData.id)
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
