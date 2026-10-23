import QtQuick 2.15
import "../theme"

Item {
    id: referenceFigure
    implicitWidth: 220
    implicitHeight: 220

    property var targetLandmarks: null
    property bool mirror: true
    property bool darkMode: true
    property string label: ""
    property string status: ""
    property string statusState: "info"

    readonly property var handConnections: [
        [0, 1], [1, 2], [2, 3], [3, 4],
        [0, 5], [5, 6], [6, 7], [7, 8],
        [0, 9], [9, 10], [10, 11], [11, 12],
        [0, 13], [13, 14], [14, 15], [15, 16],
        [0, 17], [17, 18], [18, 19], [19, 20],
        [5, 9], [9, 13], [13, 17]
    ]

    Theme { id: theme; isDark: referenceFigure.darkMode }

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        function pointAt(points, index) {
            if (!points || index >= points.length)
                return null
            var point = points[index]
            if (point === undefined || point === null)
                return null
            return {
                x: point.x !== undefined ? point.x : point[0],
                y: point.y !== undefined ? point.y : point[1]
            }
        }

        function displayPoint(point, padding) {
            padding = padding || 0.08
            return {
                x: padding + (referenceFigure.mirror ? 1 - point.x : point.x) * (1 - 2 * padding),
                y: padding + point.y * (1 - 2 * padding)
            }
        }

        function landmarkColor(point, index) {
            return theme.accent()
        }

        onPaint: {
            var context = getContext("2d")
            context.clearRect(0, 0, width, height)

            if (!referenceFigure.targetLandmarks || referenceFigure.targetLandmarks.length !== 21)
                return

            var points = []
            for (var index = 0; index < 21; index++) {
                var raw = pointAt(referenceFigure.targetLandmarks, index)
                if (raw) points[index] = displayPoint(raw)
            }

            var scale = Math.min(width, height)
            var lineWidth = Math.max(2, scale * 0.012)

            // Draw connections
            context.lineWidth = lineWidth
            context.lineCap = "round"
            context.lineJoin = "round"
            context.strokeStyle = theme.accent()
            context.globalAlpha = 0.55
            for (var line = 0; line < referenceFigure.handConnections.length; line++) {
                var pair = referenceFigure.handConnections[line]
                var start = points[pair[0]]
                var end = points[pair[1]]
                if (!start || !end) continue
                context.beginPath()
                context.moveTo(start.x * scale, start.y * scale)
                context.lineTo(end.x * scale, end.y * scale)
                context.stroke()
            }
            context.globalAlpha = 1

            // Draw joints
            var baseRadius = Math.max(4, scale * 0.018)
            for (var dot = 0; dot < points.length; dot++) {
                if (!points[dot]) continue
                var radius = (dot === 8) ? baseRadius * 1.3 : baseRadius
                var color = theme.accent()
                context.fillStyle = color
                context.beginPath()
                context.arc(points[dot].x * scale, points[dot].y * scale, radius, 0, Math.PI * 2)
                context.fill()

                // White highlight on fingertip
                if (dot === 8 || dot === 4 || dot === 12 || dot === 16 || dot === 20) {
                    context.fillStyle = theme.text()
                    context.globalAlpha = 0.4
                    context.beginPath()
                    context.arc(points[dot].x * scale, points[dot].y * scale, radius * 0.4, 0, Math.PI * 2)
                    context.fill()
                    context.globalAlpha = 1
                }
            }
        }
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        text: referenceFigure.label ? referenceFigure.label : "Reference"
        color: theme.textMuted()
        font.family: theme.fontFamily
        font.pixelSize: 14
        font.weight: Font.Medium
    }

    onTargetLandmarksChanged: canvas.requestPaint()
    onMirrorChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
}