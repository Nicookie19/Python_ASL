import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: progressScreen
    property var pipeline: null
    property var contentLoader: null

    Column {
        anchors.fill: parent
        spacing: 24
        padding: 24

        Text {
            text: "Progress"
            font.family: "Inter, sans-serif"
            font.pixelSize: 32
            font.bold: true
            color: "#FAFAFA"
        }

        Text {
            text: "Your progress will appear here"
            font.pixelSize: 16
            color: "#A1A1AA"
        }
    }
}