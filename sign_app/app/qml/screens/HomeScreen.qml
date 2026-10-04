import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "../components"
import "../theme/Theme"

Item {
    id: homeScreen
    property var contentLoader: null
    property var cameraService: null
    property var pipeline: null

    property var user: null
    property var modules: []
    property var stats: {}

    property var continueCard: null
    property var continueModule: null

    signal continueRequested(string moduleId)

    Loader {
        id: themeLoader
        sourceComponent: Theme
        onStatusChanged: {
            if (status === Loader.Ready) {
                homeScreen.theme = item
            }
        }
    }

    Component.onCompleted: {
        themeLoader.source = "theme/Theme.qml"
        refresh()
    }

    function refresh() {
        if (!user) return

        // Greeting
        greetingText.text = "Welcome back, " + user.name + "!"

        // Continue section
        buildContinueSection()

        // Modules
        buildModulesSection()

        // Stats
        buildStatsSection()

        // Quick actions
        buildActionsSection()
    }

    function setUser(userObj) {
        user = userObj
        refresh()
    }

    function buildContinueSection() {
        // Find most recently practiced incomplete module
        // This would need to be implemented in Python and exposed
    }

    function buildModulesSection() {
        // Clear existing
        while (modulesContainer.children.length > 0) {
            modulesContainer.children[0].destroy()
        }

        var pack = contentLoader.currentPack
        if (!pack) return

        var categories = [
            {category: "fingerspelling", label: "Fingerspelling"},
            {category: "numbers", label: "Numbers"},
            {catgory: "greetings", label: "Greetings"},
            {category: "phrases", label: "Phrases"}
        ]

        for (var c = 0; c < categories.length; c++) {
            var category = categories[c].category
            var label = categories[c].label

            var modules = pack.modules.filter(function(m) { return m.category === category })
            if (modules.length === 0) continue

            // Category header
            var header = categoryHeaderComponent.createObject(modulesContainer, {
                "label": label
            })

            // Module grid
            var grid = moduleGridComponent.createObject(modulesContainer)
            var progressMap = {}
            // Would need to get progress from Python

            for (var i = 0; i < modules.length; i++) {
                var module = modules[i]
                var progress = null // Would get from Python
                var card = moduleCardComponent.createObject(grid, {
                    "module": modules[i],
                    "progress": null,
                    "pack": contentLoader.currentPack
                })
            }
        }
    }

    function buildStatsSection() {
        // Stats cards
    }

    function buildActionsSection() {
        // Quick action buttons
    }

    property var contentLoader: null
    property var theme: null

    Item {
        id: root
        property var contentLoader: null
        property var theme: null
        property var user: null
        property var modules: []
        property var stats: {}

        // Main layout
        Column {
            anchors.fill: parent
            spacing: 0

            // Scroll area
            ScrollView {
                id: scrollView
                anchors.fill: parent
                clip: true
                ScrollBar.vertical: ScrollBar { }
                ScrollBar.horizontal: ScrollBar { visible: false }

                Column {
                    id: content
                    width: scrollView.width
                    spacing: 32
                    padding: 24
                    bottomPadding: 100 // Space for nav bar

                    // Greeting section
                    Row {
                        id: greetingLayout
                        spacing: 16
                        Layout.fillWidth: true

                        Text {
                            id: greetingText
                            text: "Welcome back, " + (user ? user.name : "") + "!"
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeXxxl
                            font.bold: true
                            color: theme.colorTextPrimary()
                        }

                        Item { Layout.fillWidth: true }

                        // Theme toggle
                        Button {
                            property string iconText: theme.isDark ? "☀️" : "🌙"
                            text: iconText
                            checkable: true
                            checked: theme.isDark
                            onClicked: {
                                theme.toggleTheme()
                                themeLoader.item.toggleTheme()
                            }
                            Layout.alignment: Qt.AlignRight
                            flat: true
                            font.pixelSize: 24
                        }
                    }

                    // Continue card
                    Loader {
                        id: continueLoader
                        sourceComponent: continueCardComponent
                    }

                    // Modules by category
                    Column {
                        id: modulesContainer
                        spacing: 24
                    }

                    // Stats row
                    Row {
                        id: statsLayout
                        spacing: 16
                        Layout.fillWidth: true
                    }

                    // Quick actions
                    Row {
                        id: actionsLayout
                        spacing: 12
                        Layout.fillWidth: true
                    }
                }
            }

            // ScrollView for content
            ScrollView {
                id: scrollView
                anchors.fill: parent
                clip: true
                ScrollBar.vertical: ScrollBar { }
                ScrollBar.horizontal: ScrollBar { visible: false }

                Column {
                    id: content
                    width: scrollView.width
                    spacing: 32
                    padding: 24
                    bottomPadding: 100 // Space for nav bar

                    // Greeting section
                    Row {
                        id: greetingLayout
                        spacing: 16

                        Text {
                            id: greetingText
                            text: "Welcome back, " + (user ? user.name : "") + "!"
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeXxxl
                            font.bold: true
                            color: theme.colorTextPrimary()
                        }

                        Item { Layout.fillWidth: true }

                        // Theme toggle
                        Button {
                            text: theme.isDark ? "☀️" : "🌙"
                            checkable: true
                            checked: theme.isDark
                            onClicked: {
                                theme.toggleTheme()
                            }
                            flat: true
                        }
                    }

                    // Continue card
                    Loader {
                        id: continueLoader
                        sourceComponent: continueCardComponent
                    }

                    // Modules by category
                    Column {
                        id: modulesContainer
                        spacing: 24
                    }

                    // Stats row
                    Row {
                        id: statsLayout
                        spacing: 16
                    }

                    // Quick actions
                    Row {
                        id: actionsLayout
                        spacing: 12
                    }
                }
            }
        }
    }

    Component {
        id: categoryHeaderComponent
        Item {
            property string label: ""
            width: parent ? parent.width : 0
            height: 40

            Text {
                text: label
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSizeXxl
                font.weight: Font.SemiBold
                color: theme.colorTextPrimary()
            }
        }
    }

    Component {
        id: moduleCardComponent
        Item {
            property var module: null
            property var progress: null
            property var pack: null
            width: 280
            height: 200

            Rectangle {
                anchors.fill: parent
                color: theme.colorSurface()
                border.color: theme.colorBorder()
                border.width: 1
                radius: 16

                Column {
                    anchors.fill: parent
                    spacing: 12
                    anchors.margins: 20

                    // Header
                    Row {
                        spacing: 8

                        Chip {
                            text: module.category.replace("_", " ").toUpperCase()
                            type: "category"
                        }

                        Chip {
                            text: module.difficulty
                            type: "difficulty-" + module.difficulty
                        }

                        Item { Layout.fillWidth: true }

                        Chip {
                            text: progress && progress.completed ? "Completed" :
                                  progress && progress.attempts ? "In progress" :
                                  "New"
                            type: progress && progress.completed ? "success" :
                                  progress && progress.attempts ? "category" :
                                  "difficulty-easy"
                        }
                    }

                    // Module name
                    Text {
                        text: module.name
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeXl
                        font.weight: Font.SemiBold
                        color: theme.colorTextPrimary()
                        wrapMode: Text.WordWrap
                    }

                    // Description
                    Text {
                        text: module.description
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeSm
                        color: theme.colorTextSecondary()
                        wrapMode: Text.WordWrap
                        maximumHeight: 40
                    }

                    Item { Layout.fillHeight: true }

                    // Progress
                    Row {
                        spacing: 8

                        ProgressBar {
                            id: progressBar
                            Layout.fillWidth: true
                            height: 10
                            minimum: 0
                            maximum: 100
                            value: progress ? progress.accuracy * 100 : 0
                            format: "%p%"
                            textVisible: true
                        }

                        Label {
                            text: (progress ? Math.round(module.signIds.length * (progress.accuracy || 0)) : 0) + " / " + module.signIds.length + " mastered"
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeXs
                            color: theme.colorTextDisabled()
                        }
                    }

                    // Completed label
                    Rectangle {
                        visible: progress && progress.completed
                        height: 24
                        color: "transparent"

                        Text {
                            text: "✓ Completed"
                            color: theme.colorSuccess()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeSm
                            font.bold: true
                        }
                        anchors.centerIn: parent
                    }
                }
            }
        }
    }

    Component {
        id: continueCardComponent
        Item {
            property var module: null
            property var progress: null
            width: parent ? parent.width : 0
            height: 160

            Rectangle {
                anchors.fill: parent
                color: theme.colorSurface()
                border.color: theme.colorBorder()
                border.width: 1
                radius: 16

                Row {
                    anchors.fill: parent
                    spacing: 20
                    anchors.margins: 24

                    ProgressRing {
                        progress: progress ? progress.accuracy : 0
                        size: 80
                    }

                    Column {
                        spacing: 4
                        anchors.verticalCenter: parent.verticalCenter

                        Text {
                            text: "Continue Learning"
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeXs
                            color: theme.colorTextSecondary()
                        }

                        Text {
                            text: module ? module.name : ""
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeXl
                            font.bold: true
                            color: theme.colorTextPrimary()
                        }

                        Text {
                            text: progress ? (progress.accuracy * 100).toFixed(0) + "% accuracy · " + progress.attempts + " attempts" : ""
                            font.family: theme.fontFamily
                            font.pixelSize: theme.fontSizeSm
                            color: theme.colorTextSecondary()
                        }

                        Item { Layout.fillHeight: true }

                        Button {
                            text: "Continue"
                            Layout.preferredWidth: 120
                            height: 56
                            onClicked: continueRequested(module.id)
                        }
                    }
                }
            }
        }
    }

    Component {
        id: statCardComponent
        Item {
            property string title: ""
            property string value: ""
            property string icon: ""
            property string color: ""
            width: 160
            height: 100

            Rectangle {
                anchors.fill: parent
                color: theme.colorSurface()
                border.color: theme.colorBorder()
                border.width: 1
                radius: 16

                Column {
                    anchors.fill: parent
                    spacing: 8
                    anchors.margins: 16
                    anchors.centerIn: parent

                    Text {
                        text: icon
                        font.pixelSize: 48
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: value
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeXxxl
                        font.bold: true
                        color: color
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: title
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeXs
                        color: theme.colorTextDisabled()
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }
    }

    Component {
        id: actionButtonComponent
        Button {
            property string iconChar: ""
            property string text: ""
            property string screen: ""
            property string accessibleName: text

            minimumHeight: 56
            flat: true

            Row {
                anchors.centerIn: parent
                spacing: 8

                Text {
                    text: iconChar
                    font.pixelSize: 20
                }

                Text {
                    text: text
                    font.family: theme.fontFamily
                    font.pixelSize: theme.fontSizeBase
                }
            }

            onClicked: mainWindow._showScreen(screen)
        }
    }

    function refresh() {
        if (!user) return

        greetingText.text = "Welcome back, " + user.name + "!"
        // Rebuild sections...
    }

    function buildModulesSection() {
        // Implementation would call Python to get modules and progress
    }

    function buildStatsSection() {
        // Implementation would call Python
    }

    function buildActionsSection() {
        // Create action buttons
    }

    Component.onCompleted: {
        themeLoader.source = "theme/Theme.qml"
        // Would need Python to provide user data
    }