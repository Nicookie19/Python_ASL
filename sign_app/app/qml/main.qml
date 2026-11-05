import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "screens"
import "theme"
import "components"

ApplicationWindow {
    id: appShell
    visible: true
    width: 1240
    height: 820
    minimumWidth: 720
    minimumHeight: 560
    title: "Pysign"

    property var bridgeObject: typeof bridge === "undefined" ? null : bridge
    property bool darkMode: bridgeObject ? bridgeObject.settings.theme !== "light" : true

    Theme { id: theme; isDark: appShell.darkMode }
    color: theme.background()
    palette.window: theme.background()
    palette.windowText: theme.text()
    palette.base: theme.surfaceRaised()
    palette.text: theme.text()
    palette.button: theme.surfaceRaised()
    palette.buttonText: theme.text()
    palette.highlight: theme.accent()
    palette.highlightedText: "#06212B"
    palette.placeholderText: theme.textMuted()
    palette.mid: theme.border()

    function openLibrary(mode) { pageStack.push(libraryPage, { "mode": mode }) }
    function goBack() { if (pageStack.depth > 1) pageStack.pop() }


    function openLesson(moduleId) {
        pageStack.push(lessonPage, { "moduleId": moduleId })
    }

    function openSettings() {
        pageStack.push(settingsPage)
    }

    function showNotice(message) {
        notice.text = message
        notice.open()
    }

    header: Rectangle {
        height: 68
        color: theme.surface()
        border.color: theme.border()
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: theme.space5
            anchors.rightMargin: theme.space5
            spacing: theme.space3

            Rectangle {
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                radius: 12
                color: theme.accentSoft()
                Text {
                    anchors.centerIn: parent
                    text: "✦"
                    color: theme.accent()
                    font.pixelSize: 21
                }
            }
            Text {
                text: "PYSIGN"
                color: theme.text()
                font.family: theme.fontFamily
                font.pixelSize: theme.textLg
                font.weight: Font.Bold
                font.letterSpacing: 1.5
            }
            Text {
                text: "learn by doing"
                color: theme.accent()
                font.family: theme.fontFamily
                font.pixelSize: theme.textSm
                font.weight: Font.Medium
            }
            Item { Layout.fillWidth: true }
            Button {
                id: themeToggleButton
                text: appShell.darkMode ? "☀  Light" : "◐  Dark"
                Layout.preferredHeight: 38
                onClicked: { appShell.darkMode = !appShell.darkMode; if (appShell.bridgeObject) appShell.bridgeObject.setDarkMode(appShell.darkMode) }
                background: Rectangle {
                    radius: theme.radiusPill
                    color: themeToggleButton.down ? theme.surfaceMuted() : theme.surfaceRaised()
                    border.color: theme.border()
                }
                contentItem: Text {
                    text: themeToggleButton.text
                    color: theme.textMuted()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textSm
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    StackView {
        id: pageStack
        anchors.fill: parent
        initialItem: homePage
        pushEnter: Transition { PropertyAnimation { property: "x"; from: appShell.width; to: 0; duration: 220; easing.type: Easing.OutCubic } }
        pushExit: Transition { PropertyAnimation { property: "x"; from: 0; to: -appShell.width * 0.18; duration: 180; easing.type: Easing.OutCubic } }
        popEnter: Transition { PropertyAnimation { property: "x"; from: -appShell.width * 0.18; to: 0; duration: 200; easing.type: Easing.OutCubic } }
        popExit: Transition { PropertyAnimation { property: "x"; from: 0; to: appShell.width; duration: 180; easing.type: Easing.OutCubic } }
    }

    Component {
        id: homePage
        HomeScreen {
            user: appShell.bridgeObject ? appShell.bridgeObject.currentUser : null
            stats: appShell.bridgeObject ? appShell.bridgeObject.userStats : ({})
            modules: appShell.bridgeObject ? appShell.bridgeObject.modules : []
            darkMode: appShell.darkMode
            onModuleSelected: appShell.openLesson(moduleId)
            onActionSelected: {
                if (action === "settings") {
                    appShell.openSettings()
                } else {
                    appShell.openLibrary(action)
                }
            }
        }
    }

    Component {
        id: lessonPage
        LessonScreen {
            property string moduleId: ""
            cameraImageSource: appShell.bridgeObject ? appShell.bridgeObject.cameraImageUrl : ""
            pipeline: appShell.bridgeObject
            contentLoader: appShell.bridgeObject
            cameraService: appShell.bridgeObject
            darkMode: appShell.darkMode
            onBackRequested: pageStack.pop()
            Component.onCompleted: prepare(moduleId, 0)
        }
    }

    Component {
        id: settingsPage
        SettingsScreen {
            objectName: "settingsScreen"
            pipeline: appShell.bridgeObject
            cameraService: appShell.bridgeObject
            darkMode: appShell.darkMode
            currentUser: appShell.bridgeObject ? appShell.bridgeObject.currentUser : null
            onBackRequested: pageStack.pop()
        }
    }

    Component {
        id: libraryPage
        LibraryScreen {
            pipeline: appShell.bridgeObject
            darkMode: appShell.darkMode
            onBackRequested: pageStack.pop()
            onPracticeRequested: appShell.openLesson(signId)
        }
    }

    Connections {
        target: appShell.bridgeObject
        function onStatusChanged(message, state) {
            if (state === "error" || pageStack.currentItem && pageStack.currentItem.objectName === "settingsScreen") appShell.showNotice(message)
        }
    }

    Popup {
        id: notice
        x: (appShell.width - width) / 2
        y: appShell.height - height - theme.space5
        width: Math.min(360, appShell.width - theme.space5 * 2)
        height: 48
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: theme.radiusPill
            color: theme.surfaceRaised()
            border.color: theme.border()
        }
        contentItem: Text {
            anchors.centerIn: parent
            text: notice.text
            color: theme.text()
            font.family: theme.fontFamily
            font.pixelSize: theme.textSm
            horizontalAlignment: Text.AlignHCenter
        }
        property string text: ""
        Timer { interval: 2200; running: notice.visible; onTriggered: notice.close() }
    }

    Shortcut {
        sequence: "Esc"
        enabled: pageStack.depth > 1
        onActivated: pageStack.pop()
    }
}
