// -*- coding: utf-8 -*-
import QtQuick 2.15
import QtQuick.Controls 2.15
import QmlPages 1.0
import QmlApi 1.0

Item {
    id: root
    width: 1240
    height: 780

    // ── Palette ──
    readonly property var pal: DesignTokens.palette(Theme.currentTheme)

    // ── Expose current theme for Python tests ──
    property string currentTheme: Theme.currentTheme

    // ── Background ──
    Rectangle {
        anchors.fill: parent
        color: pal.windowBg
    }

    // ── Python-callable helpers ──
    function setThemePython(t) {
        Theme.setTheme(t);
        return true;
    }

    function getThemePython() {
        return Theme.currentTheme;
    }

    function clickNav(name) {
        sidebar.activeNav = name;
        sidebar.navClicked(name);
        return contentStack.currentItem.objectName;
    }

    function setLangPython(l) {
        Theme.setLang(l);
        return true;
    }

    // ── Sidebar ──
    Sidebar {
        id: sidebar
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
    }

    // ── Content Stack ──
    StackView {
        id: contentStack
        objectName: "contentStack"
        anchors.left: sidebar.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        clip: true
        initialItem: pageVN30

        // ── Page definitions ──
        Component {
            id: pageDashboard
            DashboardPage {}
        }
        Component {
            id: pageSignals
            SignalsPage {}
        }
        Component {
            id: pageVN30
            VN30Page {}
        }
        Component {
            id: pageProfiles
            ProfilesPage {}
        }
        Component {
            id: pageCopy
            CopyPage {}
        }
        Component {
            id: pagePending
            PendingPage {}
        }
        Component {
            id: pageDiagnostics
            DiagnosticsPage {}
        }
        Component {
            id: pageSettings
            SettingsPage {}
        }

        // ── Page map for nav switching ──
        // NOTE: must be a FUNCTION (not a property initializer): an eager
        // initializer runs while the StackView body is still being created,
        // BEFORE the Component ids below exist, so a property map would be
        // full of undefined values. A function is evaluated at call time,
        // when every id is resolved.
        function pageFor(name) {
            switch (name) {
            case "Dashboard": return pageDashboard;
            case "Signals": return pageSignals;
            case "VN30": return pageVN30;
            case "Profiles": return pageProfiles;
            case "Copy": return pageCopy;
            case "Pending": return pagePending;
            case "Diagnostics": return pageDiagnostics;
            case "Settings": return pageSettings;
            }
            return null;
        }
    }

    // ── Handle nav clicks ──
    Connections {
        target: sidebar
        onNavClicked: function(name) {
            var comp = contentStack.pageFor(name);
            if (comp) {
                contentStack.replace(comp);
            }
        }
    }
}
