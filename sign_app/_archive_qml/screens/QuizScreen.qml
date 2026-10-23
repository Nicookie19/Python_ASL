import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: quizScreen
    property var pipeline: null
    property var contentLoader: null

    Column {
        anchors.fill: parent
        spacing: 24
        padding: 24

        Text {
            text: "Quiz"
            font.family: "Inter, sans-serif"
            font.pixelSize: 32
            font.bold: true
            color: "#FAFAFA"
        }

        Text {
            text: "Quiz features coming soon"
            font.pixelSize: 16
            color: "#A1A1AA"
        }
    }
}