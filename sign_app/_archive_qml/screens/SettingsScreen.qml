import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "../theme"

Item {
    id: settingsScreen
    property var pipeline: null
    property var contentLoader: null

    Column {
        anchors.fill: parent
        spacing: 24
        padding: 24

        Text {
            text: "Settings"
            font.family: "Inter, sans-serif"
            font.pixelSize: 32
            font.bold: true
            color: "#FAFAFA"
        }

        // Camera section
        Column {
            spacing: 16

            Text {
                text: "Camera"
                font.family: "Inter, sans-serif"
                font.pixelSize: 20
                font.bold: true
                color: "#FAFAFA"
            }

            Row {
                spacing: 12

                Text {
                    text: "Camera"
                    font.pixelSize: 16
                    color: "#FAFAFA"
                    Layout.fillWidth: true
                    verticalAlignment: Qt.AlignVCenter
                }

                ComboBox {
                    id: cameraCombo
                    model: ["FaceTime HD Camera", "OBS Virtual Camera"]
                    Layout.fillWidth: true
                }
            }

            Row {
                spacing: 12

                Text {
                    text: "Mirror"
                    font.pixelSize: 16
                    color: "#FAFAFA"
                    Layout.fillWidth: true
                    verticalAlignment: Qt.AlignVCenter
                }

                Switch {
                    checked: true
                }
            }
        }

        // Display section
        Column {
            spacing: 16

            Text {
                text: "Display"
                font.family: "Inter, sans-serif"
                font.pixelSize: 20
                font.bold: true
                color: "#FAFAFA"
            }

            Row {
                spacing: 12

                Text {
                    text: "Theme"
                    font.pixelSize: 16
                    color: "#FAFAFA"
                    Layout.fillWidth: true
                    verticalAlignment: Qt.AlignVCenter
                }

                ComboBox {
                    model: ["Dark", "Light"]
                    currentIndex: 0
                }
            }

            Row {
                spacing: 12

                Text {
                    text: "Text Size"
                    font.pixelSize: 16
                    color: "#FAFAFA"
                    Layout.fillWidth: true
                    verticalAlignment: Qt.AlignVCenter
                }

                Slider {
                    from: 12
                    to: 24
                    value: 16
                }
            }
        }

        // Data section
        Column {
            spacing: 16

            Text {
                text: "Data & Privacy"
                font.family: "Inter, sans-serif"
                font.pixelSize: 20
                font.bold: true
                color: "#FAFAFA"
            }

            Button {
                text: "Export My Data"
            }

            Button {
                text: "Delete All Data"
                background: Rectangle {
                    color: "#F87171"
                    radius: theme.radiusButton
                }
            }
        }
    }
}