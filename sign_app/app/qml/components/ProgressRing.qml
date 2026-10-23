import QtQuick 2.15
import "../theme"

Item {
    id: root
    implicitWidth: 72
    implicitHeight: 72

    property real progress: 0.0
    property color ringColor: theme.accent()
    property color trackColor: theme.surfaceMuted()
    property int lineWidth: 6

    Theme { id: theme }

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var context = getContext("2d")
            var radius = Math.min(width, height) / 2 - root.lineWidth / 2
            context.clearRect(0, 0, width, height)
            context.lineWidth = root.lineWidth
            context.lineCap = "round"

            context.beginPath()
            context.strokeStyle = root.trackColor
            context.arc(width / 2, height / 2, radius, 0, Math.PI * 2)
            context.stroke()

            if (root.progress > 0) {
                context.beginPath()
                context.strokeStyle = root.ringColor
                context.arc(width / 2, height / 2, radius, -Math.PI / 2,
                            -Math.PI / 2 + Math.min(1, root.progress) * Math.PI * 2)
                context.stroke()
            }
        }
    }

    onProgressChanged: canvas.requestPaint()
    onRingColorChanged: canvas.requestPaint()
    onTrackColorChanged: canvas.requestPaint()
}
