import QtQuick 2.15
import QtQuick.Controls 2.15

import "../theme"

Item {
    id: referenceAnimation
    property var landmarks: []

    implicitWidth: 300
    implicitHeight: 300

    // Skeleton connections (MediaPipe hand landmarks)
    property var connections: [
        [0, 1], [1, 2], [2, 3], [3, 4],
        [0, 5], [5, 6], [6, 7], [7, 8],
        [0, 9], [9, 10], [10, 11], [11, 12],
        [0, 13], [13, 14], [14, 15], [15, 16],
        [0, 17], [17, 18], [18, 19], [19, 20],
        [5, 9], [9, 13], [13, 17]
    ]

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            if (!referenceAnimation.landmarks || referenceAnimation.landmarks.length === 0) return

            var ctx = canvas.getContext("2d")
            ctx.clearRect(0, 0, canvas.width, canvas.height)

            // Draw connections
            ctx.strokeStyle = theme.colorAccent()
            ctx.lineWidth = 3
            ctx.lineCap = "round"
            ctx.beginPath()

            for (var i = 0; i < referenceAnimation.connections.length; i++) {
                var conn = referenceAnimation.connections[i]
                var p1 = referenceAnimation.landmarks[conn[0]]
                var p2 = referenceAnimation.landmarks[conn[1]]
                if (p1 && p2) {
                    ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height)
                    ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height)
                }
            }
            ctx.stroke()

            // Draw landmarks
            ctx.fillStyle = theme.colorAccent()
            for (var j = 0; j < referenceAnimation.landmarks.length; j++) {
                var p = referenceAnimation.landmarks[j]
                if (p) {
                    ctx.beginPath()
                    ctx.arc(p.x * canvas.width, p.y * canvas.height, 6, 0, 2 * Math.PI)
                    ctx.fill()
                }
            }
        }
    }
}