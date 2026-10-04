import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "screens"
import "components"
import "theme/Theme"

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 1200
    height: 800
    minimumWidth: 1000
    minimumHeight: 650
    title: "Sign Language Learning"
    color: theme.colorBackground()

    property var pipeline: null
    property var contentLoader: null
    property var cameraService: null
    property var currentUser: null

    // Theme management
    Loader {
        id: themeLoader
        source: "theme/Theme.qml"
        onStatusChanged: {
            if (status === Loader.Ready) {
                mainWindow.theme = item
                for (var i = 0; i < contentStack.count; i++) {
                    contentStack.get(i).theme = item
                }
            }
        }
    }

    // Performance HUD
    PerfHUD {
        id: perfHUD
    }

    // Main layout
    Column {
        anchors.fill: parent
        spacing: 0

        // Screen stack
        StackView {
            id: contentStack
            anchors.fill: parent
            initialItem: welcomeScreen
        }

        // Navigation bar (hidden during lessons/quiz)
        Rectangle {
            id: navBar
            height: 72
            color: theme.colorSurface()
            border.color: theme.colorBorder()
            border.width: 1
            visible: contentStack.currentItem !== lessonScreen && contentStack.currentItem !== quizScreen

            Row {
                anchors.fill: parent
                spacing: 8
                padding: 12

                Repeater {
                    model: [
                        {id: "home", icon: "🏠", label: "Home"},
                        {id: "dictionary", icon: "📖", label: "Dictionary"},
                        {id: "progress", icon: "📊", label: "Progress"},
                        {id: "settings", icon: "⚙️", label: "Settings"}
                    ]
                    delegate: Button {
                        text: model.icon
                        toolTip: model.label
                        checkable: true
                        checked: contentStack.currentItem === contentStack.get(index) || (model.id === "home" && contentStack.currentItem === homeScreen)
                        onClicked: contentStack.currentItem = eval(model.id + "Screen")
                        font.pixelSize: 24
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }

    // Screens
    Loader {
        id: welcomeScreen
        source: "screens/WelcomeScreen.qml"
        active: true
    }

    Component {
        id: homeScreen
        HomeScreen {}
    }

    Component {
        id: lessonScreen
        LessonScreen {}
    }

    Component {
        id: quizScreen
        QuizScreen {}
    }

    Component {
        id: dictionaryScreen
        DictionaryScreen {}
    }

    Component {
        id: progressScreen
        ProgressScreen {}
    }

    Component {
        id: instructorScreen
        InstructorScreen {}
    }

    Component {
        id: settingsScreen
        SettingsScreen {}
    }

    // Navigation functions
    function _showScreen(screenName) {
        contentStack.currentItem = eval(screenName + "Screen")
    }

    function showNavBar() {
        navBar.visible = true
    }

    function hideNavBar() {
        navBar.visible = false
    }

    // Keyboard shortcuts
    Keys.onPressed: {
        if (event.key === Qt.Key_Escape) {
            goBack()
        } else if (event.key === Qt.Key_Space) {
            spaceAction()
        } else if (event.key === Qt.Key_Left) {
            navigateRelative(-1)
        } else if (event.key === Qt.Key_Right) {
            navigateRelative(1)
        } else if (event.key === Qt.Key_Control && event.modifiers & Qt.ControlModifier && event.key === Qt.Key_D) {
            perfHUD.toggle()
        }
    }

    function goBack() {
        var current = contentStack.currentItem
        if (current && current.goBack) {
            current.goBack()
        }
    }

    function spaceAction() {
        var current = contentStack.currentItem
        if (current && current.spaceAction) {
            current.spaceAction()
        }
    }

    function navigateRelative(delta) {
        var current = contentStack.currentItem
        if (current && current.navigateRelative) {
            current.navigateRelative(delta)
        }
    }

    function goBack() {
        var current = contentStack.currentItem
        if (current && current.goBack) {
            current.goBack()
        }
    }

    function spaceAction() {
        var current = contentStack.currentItem
        if (current && current.spaceAction) {
            current.spaceAction()
        }
    }

    function navigateRelative(delta) {
        var current = contentStack.currentItem
        if (current && current.navigateRelative) {
            current.navigateRelative(delta)
        }
    }