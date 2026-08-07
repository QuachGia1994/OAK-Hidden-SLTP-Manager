// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlDesign 1.0
import QmlApi 1.0

Rectangle {
    id: root
    objectName: "page_VN30"
    color: "transparent"
    anchors.fill: parent

    readonly property var pal: DesignTokens.palette(Theme.currentTheme)
    readonly property color okGreen: root.pal.accent
    property var stocks: []
    property var filterResult: null
    property string filterText: ""
    property bool busyFilter: false
    property string errorText: ""
    property string noticeText: ""
    property string stockCountText: ""

    function s(vn, en) { return Theme.lang === "VN" ? vn : en; }

    function refreshNow() {
        var r = ShellApi.screener();
        stocks = (r && r.ok) ? r.stocks : [];
        if (!r.ok) {
            errorText = r.error || "";
        }
        stockCountText = root.s("Mã: ", "Symbols: ") + stocks.length;
    }

    function runFilterNow() {
        busyFilter = true;
        var r = ShellApi.run_filter(30);
        busyFilter = false;
        if (!r.ok) {
            errorText = r.error || "";
        } else {
            filterResult = r.result;
            if (filterResult && filterResult.status === "NO_DATA") {
                noticeText = root.s("Chưa có dữ liệu EOD trong market.db.", "No EOD data in market.db yet.");
            } else {
                noticeText = "";
            }
        }
    }

    function filteredStocks() {
        var t = filterText.trim().toUpperCase();
        if (t === "") return stocks;
        var result = [];
        for (var i = 0; i < stocks.length; i++) {
            if (String(stocks[i].symbol || "").toUpperCase().indexOf(t) >= 0) {
                result.push(stocks[i]);
            }
        }
        return result;
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
                    text: root.s("THỊ TRƯỜNG CƠ SỞ", "LOCAL EOD")
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                    color: root.pal.muted
                }
                Text {
                    text: root.s("Bộ lọc CP", "VN30 Advisor")
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
                    text: root.stockCountText
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
                    objectName: "vn30RefreshBtn"
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

        // ── Toolbar ──
        Row {
            width: parent.width
            spacing: 10

            Rectangle {
                width: 220
                height: 28
                radius: 6
                color: root.pal.surface
                border.color: vn30SearchInput.activeFocus ? root.pal.accent : root.pal.border
                border.width: 1
                objectName: "vn30Search"
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.s("Tìm mã…", "Search symbol…")
                    font.pixelSize: 12
                    color: root.pal.muted
                    visible: vn30SearchInput.text === ""
                }
                TextInput {
                    id: vn30SearchInput
                    anchors.fill: parent
                    anchors.margins: 6
                    color: root.pal.text
                    font.pixelSize: 12
                    clip: true
                    onTextChanged: root.filterText = text
                }
            }

            Item { width: parent.width - 220 - 110; height: 1 }

            Rectangle {
                width: 110
                height: 28
                radius: 6
                color: root.pal.accent
                opacity: root.busyFilter ? 0.5 : 1.0
                objectName: "runFilterBtn"
                Text {
                    text: root.busyFilter ? root.s("Đang chạy…", "Running…") : root.s("Chạy bộ lọc", "Run filter")
                    font.pixelSize: 12
                    font.bold: true
                    color: "#ffffff"
                    anchors.centerIn: parent
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: !root.busyFilter
                    onClicked: root.runFilterNow()
                }
            }
        }

        // ── Recommendations panel ──
        Rectangle {
            visible: root.filterResult !== null
            width: parent.width
            height: visible ? 226 : 0
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            radius: 8
            clip: true

            Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: root.s("Kết quả khuyến nghị", "Recommendations")
                    font.pixelSize: 13
                    font.bold: true
                    color: root.pal.text
                }

                Row {
                    spacing: 12
                    Rectangle {
                        width: buyBadge.implicitWidth + 12
                        height: 20
                        radius: 4
                        color: Qt.rgba(root.okGreen.r, root.okGreen.g, root.okGreen.b, 0.15)
                        Text {
                            id: buyBadge
                            text: "BUY " + (root.filterResult ? (root.filterResult.buy || 0) : 0)
                            font.pixelSize: 11
                            font.bold: true
                            color: root.okGreen
                            anchors.centerIn: parent
                        }
                    }
                    Rectangle {
                        width: sellBadge.implicitWidth + 12
                        height: 20
                        radius: 4
                        color: Qt.rgba(229/255, 72/255, 77/255, 0.15)
                        Text {
                            id: sellBadge
                            text: "SELL " + (root.filterResult ? (root.filterResult.sell || 0) : 0)
                            font.pixelSize: 11
                            font.bold: true
                            color: "#e5484d"
                            anchors.centerIn: parent
                        }
                    }
                    Text {
                        text: root.s("Đã quét ", "Scanned ") + (root.filterResult ? (root.filterResult.scanned || 0) : 0)
                        font.pixelSize: 11
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: root.s("Ngày dữ liệu ", "As of ") + (root.filterResult ? (root.filterResult.as_of_date || "—") : "—")
                        font.pixelSize: 11
                        color: root.pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // Header row
                Row {
                    width: parent.width
                    spacing: 8
                    Text { text: root.s("Mã", "Symbol"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 60 }
                    Text { text: root.s("Hướng", "Direction"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 70 }
                    Text { text: root.s("Điểm", "Score"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 60 }
                    Text { text: root.s("Giá đóng", "Close"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 80 }
                    Text { text: root.s("Hạng", "Rank"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 50 }
                }

                Flickable {
                    width: parent.width
                    height: 120
                    contentHeight: recColumn.height
                    clip: true

                    Column {
                        id: recColumn
                        width: parent.width

                        Repeater {
                            model: root.filterResult ? (root.filterResult.recommendations || []) : []
                            Row {
                                objectName: "recRow"
                                width: parent.width
                                spacing: 8
                                height: 22
                                Text {
                                    text: modelData.symbol || ""
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.pal.text
                                    width: 60
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: modelData.direction || ""
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: modelData.direction === "BUY" ? root.okGreen : "#e5484d"
                                    width: 70
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: modelData.score !== undefined ? Number(modelData.score).toFixed(2) : "—"
                                    font.pixelSize: 12
                                    color: root.pal.text
                                    width: 60
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: modelData.latest_close !== undefined ? Number(modelData.latest_close).toFixed(2) : "—"
                                    font.pixelSize: 12
                                    color: root.pal.text
                                    width: 80
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: modelData.rank !== undefined ? String(modelData.rank) : "—"
                                    font.pixelSize: 12
                                    color: root.pal.text
                                    width: 50
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Stocks panel ──
        Rectangle {
            width: parent.width
            height: 300
            color: root.pal.surface
            border.color: root.pal.border
            border.width: 1
            radius: 8
            clip: true

            Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: root.s("Cổ phiếu (EOD)", "Stocks (EOD)")
                    font.pixelSize: 13
                    font.bold: true
                    color: root.pal.text
                }

                // Table header
                Row {
                    width: parent.width
                    spacing: 8
                    height: 20
                    Text { text: root.s("Mã", "Symbol"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 60 }
                    Text { text: root.s("Sàn", "Exchange"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 50 }
                    Text { text: root.s("Mở", "Open"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 70 }
                    Text { text: root.s("Cao", "High"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 70 }
                    Text { text: root.s("Thấp", "Low"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 70 }
                    Text { text: root.s("Đóng", "Close"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 70 }
                    Text { text: root.s("KL", "Vol"); font.pixelSize: 11; font.bold: true; color: root.pal.muted; width: 80 }
                }

                // Empty state
                Text {
                    visible: root.filteredStocks().length === 0
                    text: root.s("Chưa có dữ liệu.", "No data yet.")
                    font.pixelSize: 12
                    color: root.pal.muted
                    objectName: "stocksEmptyText"
                }

                ListView {
                    id: stockListView
                    objectName: "stockView"
                    width: parent.width
                    height: 250
                    clip: true
                    model: root.filteredStocks()

                    delegate: Row {
                        objectName: "stockRow"
                        width: stockListView.width
                        height: 24
                        spacing: 8

                        Text {
                            text: modelData.symbol || ""
                            font.pixelSize: 12
                            font.bold: true
                            color: root.pal.text
                            width: 60
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.exchange || ""
                            font.pixelSize: 11
                            color: root.pal.muted
                            width: 50
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.open !== null && modelData.open !== undefined ? Number(modelData.open).toFixed(2) : ""
                            font.pixelSize: 11
                            color: root.pal.text
                            width: 70
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.high !== null && modelData.high !== undefined ? Number(modelData.high).toFixed(2) : ""
                            font.pixelSize: 11
                            color: root.pal.text
                            width: 70
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.low !== null && modelData.low !== undefined ? Number(modelData.low).toFixed(2) : ""
                            font.pixelSize: 11
                            color: root.pal.text
                            width: 70
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.close !== null && modelData.close !== undefined ? Number(modelData.close).toFixed(2) : ""
                            font.pixelSize: 11
                            color: root.pal.text
                            width: 70
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.volume !== null && modelData.volume !== undefined && modelData.volume > 0
                                ? Number(modelData.volume).toLocaleString(Qt.locale(), "f", 0)
                                : "—"
                            font.pixelSize: 11
                            color: root.pal.text
                            width: 80
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
}
