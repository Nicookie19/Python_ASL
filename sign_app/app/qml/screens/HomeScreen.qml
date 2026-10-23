import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "../theme"

Item {
    id: homeScreen

    property var contentLoader: null
    property var cameraService: null
    property var pipeline: null
    property bool darkMode: true
    property var user: null
    property var stats: ({})
    property var modules: []

    readonly property var exampleModules: [
        { "id": "asl_fingerspelling_1", "title": "Fingerspelling A–E", "description": "Build the five foundation handshapes.", "progress": 0.60, "lessons": 5, "tone": "cyan" },
        { "id": "asl_fingerspelling_2", "title": "Fingerspelling F–J", "description": "Practice clear finger positions and motion signs.", "progress": 0.18, "lessons": 5, "tone": "violet" },
        { "id": "asl_numbers_1", "title": "Numbers 0–5", "description": "Learn everyday number signs at a comfortable pace.", "progress": 0.00, "lessons": 6, "tone": "amber" }
    ]
    readonly property var activeModules: modules && modules.length ? modules : exampleModules
    readonly property string learnerName: user && user.name ? user.name : "Learner"

    signal moduleSelected(string moduleId)
    signal actionSelected(string action)

    Theme { id: theme; isDark: homeScreen.darkMode }

    function progressValue(module) {
        if (module.progress !== undefined) return module.progress
        return 0
    }

    function stat(name, fallback) {
        return stats && stats[name] !== undefined ? stats[name] : fallback
    }

    Rectangle {
        anchors.fill: parent
        color: theme.background()
    }

    ScrollView {
        id: homeScroll
        anchors.fill: parent
        clip: true
        // Give the Flickable an explicit, viewport-sized content area.  The
        // previous centered child used the Flickable's transient content
        // width and could shift the first dashboard column off-screen.
        contentWidth: width
        contentHeight: dashboard.implicitHeight + theme.space5 * 2
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            id: dashboard
            x: theme.space6
            y: theme.space5
            width: Math.max(0, homeScroll.availableWidth - theme.space6 * 2)
            spacing: theme.space6

            RowLayout {
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: theme.space1
                    Text {
                        text: "Welcome back, " + homeScreen.learnerName
                        color: theme.text()
                        font.family: theme.fontFamily
                        font.pixelSize: theme.text2Xl
                        font.weight: Font.Bold
                    }
                    Text {
                        text: "A few focused minutes today will make your signs feel more natural."
                        color: theme.textMuted()
                        font.family: theme.fontFamily
                        font.pixelSize: theme.textMd
                    }
                }

                Rectangle {
                    Layout.preferredWidth: streakLabel.implicitWidth + theme.space4 * 2
                    Layout.preferredHeight: 40
                    radius: 20
                    color: theme.warningSoft()
                    Row {
                        anchors.centerIn: parent
                        spacing: theme.space2
                        Text { text: "◆"; color: theme.warning(); font.pixelSize: 14 }
                        Text {
                            id: streakLabel
                            text: homeScreen.stat("streak", 0) + " day streak"
                            color: theme.warning()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 206
                radius: theme.radiusLg
                color: theme.accentSoft()
                border.color: "#2B647A"

                Rectangle {
                    width: 260; height: 260; radius: 130
                    x: parent.width - width * 0.67; y: -height * 0.42
                    color: "#1A6E87"
                    opacity: 0.34
                }
                Rectangle {
                    width: 180; height: 180; radius: 90
                    x: parent.width - width * 0.35; y: parent.height - height * 0.38
                    color: "#49D0EE"
                    opacity: 0.10
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space6
                    spacing: theme.space5

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: theme.space2
                        Text {
                            text: "Continue where you left off"
                            color: theme.textMuted()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: homeScreen.activeModules[0].title
                            color: theme.text()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textXl
                            font.weight: Font.Bold
                        }
                        Text {
                            text: Math.round(homeScreen.progressValue(homeScreen.activeModules[0]) * 100) + "% complete  •  " + homeScreen.activeModules[0].lessons + " signs"
                            color: theme.textMuted()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                        }
                        Item { Layout.fillHeight: true }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 8
                            radius: 4
                            color: "#24546A"
                            Rectangle {
                                width: parent.width * homeScreen.progressValue(homeScreen.activeModules[0])
                                height: parent.height
                                radius: parent.radius
                                color: theme.accent()
                            }
                        }
                    }

                    Button {
                        id: resumeButton
                        text: "Resume  ›"
                        Layout.preferredWidth: 128
                        Layout.preferredHeight: 48
                        onClicked: homeScreen.moduleSelected(homeScreen.activeModules[0].id)
                        background: Rectangle {
                            radius: theme.radiusSm
                            color: resumeButton.down ? theme.accentStrong() : theme.accent()
                        }
                        contentItem: Text {
                            text: resumeButton.text
                            color: "#06212B"
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                            font.weight: Font.Bold
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 920 ? 4 : 2
                columnSpacing: theme.space3
                rowSpacing: theme.space3

                Repeater {
                    model: [
                        { "value": homeScreen.stat("accuracy", 0) + "%", "label": "Accuracy", "accent": theme.accent() },
                        { "value": homeScreen.stat("completedModules", 0), "label": "Modules completed", "accent": theme.success() },
                        { "value": homeScreen.stat("totalMinutes", 0) + "m", "label": "Practice time", "accent": theme.warning() },
                        { "value": homeScreen.activeModules.length, "label": "Lessons ready", "accent": theme.text() }
                    ]
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 112
                        radius: theme.radiusMd
                        color: theme.surface()
                        border.color: theme.border()
                        required property var modelData
                        Column {
                            anchors.fill: parent
                            anchors.margins: theme.space4
                            spacing: theme.space2
                            Text {
                                text: modelData.value
                                color: modelData.accent
                                font.family: theme.fontFamily
                                font.pixelSize: theme.textXl
                                font.weight: Font.Bold
                            }
                            Text {
                                text: modelData.label
                                color: theme.textMuted()
                                font.family: theme.fontFamily
                                font.pixelSize: theme.textSm
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Keep learning"
                    color: theme.text()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textXl
                    font.weight: Font.Bold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: homeScreen.activeModules.length + " lessons"
                    color: theme.textMuted()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textSm
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 980 ? 3 : (width >= 640 ? 2 : 1)
                columnSpacing: theme.space4
                rowSpacing: theme.space4

                Repeater {
                    model: homeScreen.activeModules
                    delegate: Rectangle {
                        required property var modelData
                        readonly property var module: modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 218
                        radius: theme.radiusMd
                        color: theme.surface()
                        border.color: theme.border()

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: theme.space4
                            spacing: theme.space3

                            RowLayout {
                                Layout.fillWidth: true
                                Rectangle {
                                    Layout.preferredWidth: 34
                                    Layout.preferredHeight: 34
                                    radius: 17
                                    color: module.tone === "amber" ? theme.warningSoft()
                                           : module.tone === "violet" ? "#2F285A" : theme.accentSoft()
                                    Text {
                                        anchors.centerIn: parent
                                        text: module.tone === "amber" ? "#" : module.tone === "violet" ? "✦" : "⌁"
                                        color: module.tone === "amber" ? theme.warning()
                                               : module.tone === "violet" ? "#B9A9FF" : theme.accent()
                                        font.pixelSize: 16
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: Math.round(homeScreen.progressValue(module) * 100) + "%"
                                    color: theme.textMuted()
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.textSm
                                    font.weight: Font.DemiBold
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: module.title || module.name || "Untitled lesson"
                                color: theme.text()
                                font.family: theme.fontFamily
                                font.pixelSize: theme.textLg
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: module.description || "Practice a new sign set with guided feedback."
                                color: theme.textMuted()
                                font.family: theme.fontFamily
                                font.pixelSize: theme.textSm
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 6
                                radius: 3
                                color: theme.surfaceMuted()
                                Rectangle {
                                    width: parent.width * homeScreen.progressValue(module)
                                    height: parent.height
                                    radius: parent.radius
                                    color: theme.accent()
                                }
                            }
                            Button {
                                id: moduleActionButton
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                text: homeScreen.progressValue(module) > 0 ? "Continue" : "Start lesson"
                                onClicked: homeScreen.moduleSelected(module.id)
                                background: Rectangle {
                                    radius: theme.radiusSm
                                    color: moduleActionButton.down ? theme.surfaceMuted() : theme.surfaceRaised()
                                    border.color: theme.border()
                                }
                                contentItem: Text {
                                    text: moduleActionButton.text
                                    color: theme.text()
                                    font.family: theme.fontFamily
                                    font.pixelSize: theme.textSm
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 88
                radius: theme.radiusMd
                color: theme.surface()
                border.color: theme.border()

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space4
                    spacing: theme.space3
                    Repeater {
                        model: [
                            { "label": "Dictionary", "icon": "⌕", "action": "dictionary" },
                            { "label": "Progress", "icon": "◌", "action": "progress" },
                            { "label": "Quick quiz", "icon": "✦", "action": "quiz" },
                            { "label": "Settings", "icon": "⚙", "action": "settings" }
                        ]
                        delegate: Button {
                            id: quickActionButton
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 56
                            text: modelData.icon + "  " + modelData.label
                            onClicked: homeScreen.actionSelected(modelData.action)
                            background: Rectangle {
                                radius: theme.radiusSm
                                color: quickActionButton.down ? theme.surfaceMuted() : "transparent"
                            }
                            contentItem: Text {
                                text: quickActionButton.text
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
            }
        }
    }
}
