import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

Item {
    id: screen
    property var pipeline: null
    property var cameraService: null
    property var currentUser: null
    property bool darkMode: true
    property var devices: pipeline ? pipeline.cameras() : []
    signal backRequested()
    Theme { id: theme; isDark: screen.darkMode }
    Rectangle { anchors.fill: parent; color: theme.background() }
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 24
            Item { Layout.preferredHeight: 8 }
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 24
                Button { text: "‹ Back"; onClicked: screen.backRequested() }
                Label { text: "Make yourself at home"; color: theme.text(); font.pixelSize: 26; font.bold: true }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.leftMargin: 24; Layout.rightMargin: 24
                implicitHeight: form.implicitHeight + 48
                radius: 20; color: theme.surface(); border.color: theme.border()
                ColumnLayout {
                    id: form
                    anchors.fill: parent; anchors.margins: 24; spacing: 16
                    Label { text: "YOUR PROFILE"; color: theme.accent(); font.bold: true }
                    Label { text: "Learner name"; color: theme.text() }
                    TextField { id: nameField; Layout.fillWidth: true; text: screen.currentUser ? screen.currentUser.name : "Learner"; maximumLength: 80; Accessible.name: "Learner name" }
                    Label { text: "PRACTICE CAMERA"; color: theme.accent(); font.bold: true }
                    ComboBox {
                        id: cameraPicker; Layout.fillWidth: true
                        model: screen.devices; textRole: "name"; valueRole: "id"
                        Component.onCompleted: {
                            if (pipeline) for (var i=0; i<screen.devices.length; i++)
                                if (screen.devices[i].id === pipeline.settings.camera_device_id) currentIndex=i
                        }
                        Accessible.name: "Camera device"
                    }
                    Label { visible: !screen.devices.length; text: "No camera detected. Connect a webcam, then refresh."; color: theme.warning() }
                    Button { text: "Refresh cameras"; onClicked: screen.devices = pipeline.cameras() }
                    CheckBox { id: mirror; text: "Mirror my camera"; checked: pipeline ? pipeline.settings.mirror_camera : true }
                    Label { text: "PRIVACY & RECOGNITION"; color: theme.accent(); font.bold: true }
                    Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: theme.textMuted()
                        text: "Your profile and practice history stay on this computer. The app does not record camera video. Use the Light / Dark button above to change your theme."
                    }
                    Label {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: theme.textMuted()
                        text: pipeline && pipeline.modelAvailable ? "Trained recognition model loaded. Motion signs remain self-guided." : "No trained recognition model installed. Camera tracking and self-guided lessons are available; reviewed signs do not count as correct recognition."
                    }
                    Button {
                        text: "Save preferences"; highlighted: true; Layout.preferredHeight: 46
                        onClicked: pipeline.saveSettings(nameField.text, cameraPicker.currentValue || "", mirror.checked, screen.darkMode ? "dark" : "light")
                    }
                }
            }
            Item { Layout.preferredHeight: 24 }
        }
    }
}
