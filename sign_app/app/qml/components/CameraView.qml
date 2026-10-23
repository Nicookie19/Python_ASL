import QtQuick 2.15
import "../theme"

Item {
    id: cameraView
    implicitWidth: 720
    implicitHeight: 440

    // A URL served by the bridge's image provider. Image is deliberately used
    // here instead of a second QML camera instance, so the app has exactly one
    // camera owner: the Python CameraService.
    property string imageSource: ""
    property var hands: []
    property var targetLandmarks: null
    property bool mirror: true
    property string statusText: "Position one hand in the frame"
    property string statusState: "info"
    property bool showFps: false
    property real fps: 0.0
    property string cameraName: "Camera"
    property bool darkMode: true

    // Computed match quality (0.0 to 1.0) between user hand and target
    readonly property real matchQuality: (() => {
        if (!cameraView.targetLandmarks || cameraView.targetLandmarks.length !== 21 ||
            !cameraView.hands || cameraView.hands.length === 0)
            return 0
        var target = cameraView.targetLandmarks
        var user = cameraView.hands[0].landmarks || cameraView.hands[0]
        var totalDist = 0
        var count = 0
        for (var i = 0; i < 21; i++) {
            if (target[i] && user[i]) {
                var dx = target[i].x - user[i].x
                var dy = target[i].y - user[i].y
                totalDist += Math.sqrt(dx * dx + dy * dy)
                count++
            }
        }
        if (count === 0) return 0
        var avgDist = totalDist / count
        // Convert distance to quality: <0.05 = 1.0, >0.15 = 0.0
        return Math.max(0, Math.min(1, 1 - (avgDist - 0.05) / 0.10))
    })()

    readonly property var handConnections: [
        [0, 1], [1, 2], [2, 3], [3, 4],
        [0, 5], [5, 6], [6, 7], [7, 8],
        [0, 9], [9, 10], [10, 11], [11, 12],
        [0, 13], [13, 14], [14, 15], [15, 16],
        [0, 17], [17, 18], [18, 19], [19, 20],
        [5, 9], [9, 13], [13, 17]
    ]

    Theme { id: theme; isDark: cameraView.darkMode }

    Rectangle {
        id: viewport
        anchors.fill: parent
        radius: theme.radiusLg
        color: "#070D17"
        border.width: 1
        border.color: cameraView.hands && cameraView.hands.length > 0
                      ? theme.accent() : theme.border()
        clip: true

        Behavior on border.color { ColorAnimation { duration: 160 } }

        Image {
            id: videoPreview
            anchors.fill: parent
            source: cameraView.imageSource
            cache: false
            fillMode: Image.PreserveAspectFit
            mirror: cameraView.mirror
        }

        // A quiet empty state makes the preview feel purposeful before the
        // native video source is attached.
        Column {
            anchors.centerIn: parent
            visible: !cameraView.imageSource
            spacing: theme.space2

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "⌁"
                color: theme.accent()
                font.family: theme.fontFamily
                font.pixelSize: 42
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Camera preview will appear here"
                color: theme.textMuted()
                font.family: theme.fontFamily
                font.pixelSize: theme.textMd
            }
        }

        Canvas {
            id: skeletonCanvas
            anchors.fill: parent
            antialiasing: true

            property var targetPoints: []
            property bool showTargetOnly: false

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

            function drawPoint(context, point, radius, color) {
                context.beginPath()
                context.fillStyle = color
                context.arc(point.x, point.y, radius, 0, Math.PI * 2)
                context.fill()
            }

            function drawPointWithStroke(context, point, radius, fillColor, strokeColor, strokeWidth) {
                context.beginPath()
                context.fillStyle = fillColor
                context.arc(point.x, point.y, radius, 0, Math.PI * 2)
                context.fill()
                if (strokeWidth > 0) {
                    context.strokeStyle = strokeColor
                    context.lineWidth = strokeWidth
                    context.stroke()
                }
            }

            function displayPoint(point) {
                var previewWidth = videoPreview.paintedWidth > 0 ? videoPreview.paintedWidth : width
                var previewHeight = videoPreview.paintedHeight > 0 ? videoPreview.paintedHeight : height
                var rect = Qt.rect((width - previewWidth) / 2,
                                   (height - previewHeight) / 2,
                                   previewWidth, previewHeight)
                return {
                    x: rect.x + (cameraView.mirror ? 1 - point.x : point.x) * rect.width,
                    y: rect.y + point.y * rect.height
                }
            }

            function landmarkColor(point, index) {
                return theme.accent()
            }

            function targetLandmarkColor(index) {
                var target = pointAt(cameraView.targetLandmarks, index)
                if (!target)
                    return theme.accent()
                var userPoint = null
                if (cameraView.hands && cameraView.hands.length > 0) {
                    var landmarks = cameraView.hands[0].landmarks || cameraView.hands[0]
                    userPoint = pointAt(landmarks, index)
                }
                if (!userPoint)
                    return theme.accent()
                var distance = Math.sqrt(Math.pow(target.x - userPoint.x, 2)
                                         + Math.pow(target.y - userPoint.y, 2))
                if (distance < 0.05) return theme.success()
                if (distance < 0.12) return theme.warning()
                return theme.danger()
            }

            onPaint: {
                var context = getContext("2d")
                context.clearRect(0, 0, width, height)

                if (!cameraView.hands || cameraView.hands.length === 0)
                    return

                // Draw user hand
                context.lineWidth = 3
                context.lineCap = "round"
                context.lineJoin = "round"

                for (var handIndex = 0; handIndex < cameraView.hands.length; handIndex++) {
                    var hand = cameraView.hands[handIndex]
                    var landmarks = hand.landmarks || hand
                    var points = []
                    for (var index = 0; index < 21; index++) {
                        var raw = pointAt(landmarks, index)
                        if (raw) points[index] = displayPoint(raw)
                    }

                    for (var line = 0; line < cameraView.handConnections.length; line++) {
                        var pair = cameraView.handConnections[line]
                        var start = points[pair[0]]
                        var end = points[pair[1]]
                        if (!start || !end) continue
                        context.strokeStyle = theme.accent()
                        context.globalAlpha = 0.9
                        context.beginPath()
                        context.moveTo(start.x, start.y)
                        context.lineTo(end.x, end.y)
                        context.stroke()
                    }

                    context.globalAlpha = 1
                    for (var dot = 0; dot < points.length; dot++) {
                        if (points[dot])
                            drawPoint(context, points[dot], dot === 8 ? 6 : 4,
                                      landmarkColor(pointAt(landmarks, dot), dot))
                    }
                }
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: theme.space3
            width: cameraPill.implicitWidth + theme.space3 * 2
            height: 30
            radius: height / 2
            color: "#B8070D17"

            Row {
                id: cameraPill
                anchors.centerIn: parent
                spacing: theme.space2
                Rectangle {
                    width: 7; height: 7; radius: 4
                    color: cameraView.hands && cameraView.hands.length > 0
                           ? theme.success() : theme.accent()
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: cameraView.cameraName
                    color: theme.text()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textXs
                    font.weight: Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: theme.space3
            visible: cameraView.showFps && cameraView.fps > 0
            width: fpsText.implicitWidth + theme.space3 * 2
            height: 30
            radius: height / 2
            color: "#B8070D17"
            Text {
                id: fpsText
                anchors.centerIn: parent
                text: Math.round(cameraView.fps) + " FPS"
                color: theme.text()
                font.family: theme.fontFamily
                font.pixelSize: theme.textXs
                font.weight: Font.DemiBold
            }
}

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: theme.space3
            width: Math.min(parent.width - theme.space5 * 2, statusLabel.implicitWidth + theme.space5)
            height: Math.max(34, statusLabel.implicitHeight + theme.space3)
            radius: height / 2
            color: theme.stateSurface(cameraView.statusState)
            border.width: 1
            border.color: theme.stateColor(cameraView.statusState)
            visible: cameraView.statusText.length > 0

            Text {
                id: statusLabel
                anchors.centerIn: parent
                width: parent.width - theme.space5
                text: cameraView.statusText
                color: theme.stateColor(cameraView.statusState)
                font.family: theme.fontFamily
                font.pixelSize: theme.textSm
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }
    }

    onHandsChanged: skeletonCanvas.requestPaint()
    onTargetLandmarksChanged: {}
    onMirrorChanged: skeletonCanvas.requestPaint()
    onWidthChanged: skeletonCanvas.requestPaint()
    onHeightChanged: skeletonCanvas.requestPaint()
}
