import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

Item {
    id: welcomeScreen
    property var pipeline: null

    Column {
        anchors.fill: parent
        spacing: 32
        anchors.margins: 48

        Text {
            text: "Welcome to Sign Language Learning"
            font.family: theme.fontFamily
            font.pixelSize: theme.fontSizeDisplay
            font.bold: true
            color: theme.colorTextPrimary()
            horizontalAlignment: Qt.AlignHCenter
        }

        Text {
            text: "Learn ASL fingerspelling with real-time hand tracking"
            font.family: theme.fontFamily
            font.pixelSize: theme.fontSizeBody
            color: theme.colorTextSecondary()
            horizontalAlignment: Qt.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Column {
            spacing: 16
            anchors.horizontalCenter: parent.horizontalCenter

            TextField {
                id: nameInput
                placeholderText: "Enter your name"
                Layout.fillWidth: true
                Layout.minimumWidth: 300
            }

            Button {
                text: "Continue"
                Layout.fillWidth: true
                Layout.minimumWidth: 200
                enabled: nameInput.text.length > 0
                onClicked: {
                    bridge.showScreen("home")
                    bridge.createUser(nameInput.text)
                }
            }

            Text {
                text: "By continuing, you agree to our Privacy Policy and Terms of Service."
                font.family: theme.fontFamily
                font.pixelSize: theme.fontSizeCaption
                color: theme.colorTextDisabled()
                horizontalAlignment: Qt.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }
    }
}