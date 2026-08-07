// -*- coding: utf-8 -*-
import QtQuick 2.15
import QmlApi 1.0

Rectangle {
    id: sidebar
    width: 330
    height: parent ? parent.height : 780

    // ── Signals ──
    signal navClicked(string name)

    // ── State ──
    property string activeNav: "VN30"

    // ── Palette (reactive to theme) ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    color: pal.surface

    // ── Data ──
    readonly property var navItems: [
        { key: "Dashboard",  icon: "▦",  labelEN: "Dashboard",     labelVN: "Bảng điều khiển" },
        { key: "Signals",    icon: "⌁",  labelEN: "Signals",       labelVN: "Tín hiệu" },
        { key: "VN30",       icon: "◌",  labelEN: "VN30 Advisor",  labelVN: "Bộ lọc CP" },
        { key: "Profiles",   icon: "▣",  labelEN: "Profiles",      labelVN: "Hồ sơ" },
        { key: "Copy",       icon: "♧",  labelEN: "Copy",          labelVN: "Sao chép" },
        { key: "Pending",    icon: "◷",  labelEN: "Pending",       labelVN: "Lệnh chờ" },
        { key: "Diagnostics",icon: "⌁",  labelEN: "Diagnostics",   labelVN: "Chẩn đoán" },
        { key: "Settings",   icon: "⚙",  labelEN: "Settings",      labelVN: "Cài đặt" }
    ]

    readonly property var analysisItems: [
        { icon: "◎", labelEN: "Accounts",    labelVN: "Tài khoản" },
        { icon: "↗", labelEN: "Performance", labelVN: "Hiệu suất" },
        { icon: "⧗", labelEN: "History",     labelVN: "Lịch sử" },
        { icon: "§", labelEN: "Rules today", labelVN: "Quy tắc hôm nay" },
        { icon: "◈", labelEN: "News",        labelVN: "Tin tức" }
    ]

    function navLabel(item) {
        return Theme.lang === "VN" ? item.labelVN : item.labelEN;
    }

    function sectionLabel(vn, en) {
        return Theme.lang === "VN" ? vn : en;
    }

    // ── Persist rail prefs to settings.json (parity with oak_qt_shell) ──
    function cycleThemePersist() {
        Theme.toggleTheme();
        ShellApi.settings_update(JSON.stringify({theme: Theme.currentTheme}));
    }

    function setLangPersist(l) {
        Theme.setLang(l);
        ShellApi.settings_update(JSON.stringify({lang: Theme.lang}));
    }

    Column {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 10
        spacing: 0

        // ── Brand row ──
        Item {
            width: parent.width
            height: 32
            Text {
                text: "⚡ OAK Manager"
                font.pixelSize: 16
                font.bold: true
                color: pal.accent
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // ── Section: VẬN HÀNH ──
        Item {
            width: parent.width
            height: 22
            Text {
                text: sectionLabel("VẬN HÀNH", "OPERATIONS")
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 2
                color: pal.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // ── 8 nav buttons ──
        Repeater {
            model: sidebar.navItems
            delegate: Item {
                objectName: "nav_" + modelData.key
                width: parent.width
                height: 36
                property bool isActive: sidebar.activeNav === modelData.key

                Rectangle {
                    anchors.fill: parent
                    anchors.topMargin: 2
                    anchors.bottomMargin: 2
                    radius: 14
                    color: isActive ? pal.navActiveBg : "transparent"

                    // Left accent strip for active
                    Rectangle {
                        visible: isActive
                        width: 3
                        height: parent.height - 4
                        radius: 1
                        color: pal.navActiveLeft
                        anchors.left: parent.left
                        anchors.leftMargin: 0
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        spacing: 8
                        Text {
                            text: modelData.icon
                            font.pixelSize: 14
                            color: isActive ? pal.text : pal.muted
                            font.bold: isActive
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: sidebar.navLabel(modelData)
                            font.pixelSize: 14
                            color: isActive ? pal.text : pal.muted
                            font.bold: isActive
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            sidebar.activeNav = modelData.key;
                            sidebar.navClicked(modelData.key);
                        }
                    }
                }
            }
        }

        // ── Spacer before divider ──
        Item { width: parent.width; height: 6 }

        // ── Divider 1 ──
        Rectangle {
            id: divider1
            width: parent.width
            height: 1
            color: pal.divider
            objectName: "divider1"
        }

        // ── Spacer after divider ──
        Item { width: parent.width; height: 6 }

        // ── Section: PHÂN TÍCH ──
        Item {
            width: parent.width
            height: 22
            Text {
                text: sectionLabel("PHÂN TÍCH", "ANALYSIS")
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 2
                color: pal.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // ── 5 placeholder rows (disabled, muted 50%) ──
        Repeater {
            model: sidebar.analysisItems
            delegate: Item {
                width: parent.width
                height: 30
                opacity: 0.5
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    spacing: 8
                    Text {
                        text: modelData.icon
                        font.pixelSize: 13
                        color: pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: sidebar.navLabel(modelData)
                        font.pixelSize: 13
                        color: pal.muted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        // ── Spacer ──
        Item { width: parent.width; height: 6 }

        // ── Divider 2 ──
        Rectangle {
            id: divider2
            width: parent.width
            height: 1
            color: pal.divider
            objectName: "divider2"
        }

        // ── Spacer ──
        Item { width: parent.width; height: 6 }

        // ── Section: HỒ SƠ ──
        Item {
            width: parent.width
            height: 22
            Text {
                text: sectionLabel("HỒ SƠ", "PROFILES")
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 2
                color: pal.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // ── Input-like row: "Vantage" ──
        Rectangle {
            width: parent.width
            height: 38
            radius: 8
            color: pal.surface
            border.color: pal.border
            border.width: 1
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 10
                spacing: 6
                Text {
                    text: "▣"
                    font.pixelSize: 13
                    color: pal.muted
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "Vantage"
                    font.pixelSize: 13
                    color: pal.text
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        // ── Spacer ──
        Item { width: parent.width; height: 4 }

        // ── Status + Start button row ──
        Item {
            width: parent.width
            height: 36
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.right: parent.right
                anchors.rightMargin: 10
                spacing: 8
                Text {
                    text: "Stopped"
                    font.pixelSize: 12
                    color: pal.muted
                    anchors.verticalCenter: parent.verticalCenter
                }
                Item { width: parent.width - startBtn.width - 100; height: 1 }
                Rectangle {
                    id: startBtn
                    width: 120
                    height: 28
                    radius: 14
                    color: pal.accent
                    Text {
                        text: sectionLabel("Chạy profile đã chọn", "Start selected")
                        font.pixelSize: 12
                        font.bold: true
                        color: "#ffffff"
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                    }
                }
            }
        }

        // ── Spacer ──
        Item { width: parent.width; height: 6 }

        // ── Divider 3 ──
        Rectangle {
            id: divider3
            width: parent.width
            height: 1
            color: pal.divider
            objectName: "divider3"
        }

        // ── Spacer ──
        Item { width: parent.width; height: 6 }

        // ── Section: TRẠNG THÁI TRỰC TUYẾN ──
        Item {
            width: parent.width
            height: 22
            Text {
                text: sectionLabel("TRẠNG THÁI TRỰC TUYẾN", "LIVE STATUS")
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 2
                color: pal.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // ── Status text ──
        Item {
            width: parent.width
            height: 22
            Text {
                text: "Heartbeat ready"
                font.pixelSize: 12
                color: pal.muted
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 10
            }
        }

        // ── Prefs row: lang toggle + theme cycle ──
        Item {
            id: prefsRow
            width: parent.width
            height: 32
            objectName: "prefsRow"
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 10
                spacing: 6

                // EN button
                Rectangle {
                    width: 36
                    height: 26
                    radius: 4
                    color: Theme.lang === "EN" ? Qt.rgba(pal.accent.r, pal.accent.g, pal.accent.b, 0.15) : "transparent"
                    border.color: pal.border
                    border.width: 1
                    Text {
                        text: "EN"
                        font.pixelSize: 11
                        font.bold: Theme.lang === "EN"
                        color: Theme.lang === "EN" ? pal.accent : pal.muted
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: sidebar.setLangPersist("EN")
                    }
                }

                // VN button
                Rectangle {
                    width: 36
                    height: 26
                    radius: 4
                    color: Theme.lang === "VN" ? Qt.rgba(pal.accent.r, pal.accent.g, pal.accent.b, 0.15) : "transparent"
                    border.color: pal.border
                    border.width: 1
                    Text {
                        text: "VN"
                        font.pixelSize: 11
                        font.bold: Theme.lang === "VN"
                        color: Theme.lang === "VN" ? pal.accent : pal.muted
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: sidebar.setLangPersist("VN")
                    }
                }

                // Theme cycle button
                Rectangle {
                    width: 100
                    height: 26
                    radius: 4
                    color: "transparent"
                    border.color: pal.border
                    border.width: 1
                    Text {
                        text: Theme.currentTheme
                        font.pixelSize: 11
                        color: pal.muted
                        anchors.centerIn: parent
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: sidebar.cycleThemePersist()
                    }
                    objectName: "themeToggle"
                }
            }
        }
    }
}
