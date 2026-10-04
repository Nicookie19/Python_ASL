import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Shapes 2.15

Item {
    id: cameraView
    property var frame: null
    property var hands: []
    property var targetLandmarks: null
    property bool mirror: true
    property string statusText: ""
    property string statusState: "info"
    property bool showFps: false
    property real fps: 0.0

    // Skeleton connections
    property var connections: [
        [0, 1], [1, 2], [2, 3], [3, 4],
        [0, 5], [5, 6], [6, 7], [7, 8],
        [0, 9], [9, 10], [10, 11], [11, 12],
        [0, 13], [13, 14], [14, 15], [15, 16],
        [0, 17], [17, 18], [18, 19], [19, 20],
        [5, 9], [9, 13], [13, 17]
    ]

    property var theme: Theme

    property alias frame: videoOutput.source

    property var _hands: []
    property var _targetLandmarks: null
    property bool _mirror: true

    property var _frame: null
    property string _statusText: ""
    property string _statusState: "info"
    property bool _showFps: false
    property real _fps: 0.0

    property var _hands: []
    property var _targetLandmarks: null

    width: 640
    height: 480
    minimumWidth: 640
    minimumHeight: 360

    property alias mirror: videoOutput.mirror
    property alias statusText: statusText
    property alias statusState: statusState

    Rectangle {
        id: background
        anchors.fill: parent
        color: "#000000"
        radius: 16
        clip: true

        VideoOutput {
            id: videoOutput
            anchors.fill: parent
            fillMode: VideoOutput.PreserveAspectFit
            mirror: cameraView.mirror
        }

        // Skeleton overlay
        Canvas {
            id: skeletonCanvas
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                if (cameraView._hands && cameraView._hands.length > 0) {
                    drawSkeleton(ctx)
                }
            }

            function drawSkeleton(ctx) {
                var palette = theme
                var widgetRect = cameraView

                for (var h = 0; h < cameraView._hands.length; h++) {
                    var hand = cameraView._hands[h]
                    var coords = hand.landmarks
                    var connections = [
                        [0, 1], [1, 2], [2, 3], [3, 4],
                        [0, 5], [5, 6], [6, 7], [7, 8],
                        [0, 9], [9, 10], [10, 11], [11, 12],
                        [0, 13], [13, 14], [14, 15], [15, 16],
                        [0, 17], [17, 18], [18, 19], [19, 20],
                        [5, 9], [9, 13], [13, 17]
                    ]

                    var w = cameraView.width
                    var h = cameraView.height

                    // Calculate scale and offset
                    var frameW = cameraView._frame ? cameraView._frame.width : cameraView.width
                    var frameH = cameraView._frame ? cameraView._frame.height : cameraView.height
                    var scaleW = cameraView.width / frameW
                    var scaleH = cameraView.height / frameH
                    var scale = Math.min(scaleW, scaleH)
                    var drawW = frameW * scale
                    var drawH = frameH * scale
                    var x = (cameraView.width - drawW) / 2
                    var y = (cameraView.height - drawH) / 2
                    var flipX = cameraView.mirror

                    for (var h = 0; h < cameraView._hands.length; h++) {
                        var hand = cameraView._hands[h]
                        var coords = []
                        for (var i = 0; i < 21; i++) {
                            var lm = hand.landmarks[i]
                            var cx = lm[0] * cameraView.width
                            var cy = lm[1] * cameraView.height
                            if (cameraView.mirror) {
                                cx = cameraView.width - cx
                            }
                            coords.push({x: cx, y: cy})
                        }

                        // Determine colors based on correctness
                        var colors = []
                        if (cameraView._targetLandmarks) {
                            var targetCoords = []
                            for (var i = 0; i < 21; i++) {
                                var lm = cameraView._targetLandmarks[i]
                                var cx = lm[0] * cameraView.width
                                var cy = lm[1] * cameraView.height
                                if (cameraView.mirror) {
                                    cx = cameraView.width - cx
                                }
                                targetCoords.push({x: cx, y: cy})
                            }
                            for (var i = 0; i < 21; i++) {
                                var dist = Math.sqrt(
                                    Math.pow(coords[i].x - targetCoords[i].x, 2) +
                                    Math.pow(coords[i].y - targetCoords[i].y, 2)
                                )
                                var normDist = dist / Math.max(cameraView.width, cameraView.height)
                                if (normDist < 0.05) {
                                    colors.push(Qt.rgba(0.29, 0.87, 0.5, 1)) // success green
                                } else if (normDist < 0.12) {
                                    colors.push(Qt.rgba(0.98, 0.73, 0.15, 1)) // warning yellow
                                } else {
                                    colors.push(Qt.rgba(0.97, 0.44, 0.44, 1)) // error red
                                }
                            }
                        } else {
                            for (var i = 0; i < 21; i++) {
                                colors.push(Qt.rgba(0.63, 0.63, 0.67, 1)) // neutral
                            }
                        }

                        // Draw connections
                        var connections = [
                            [0, 1], [1, 2], [2, 3], [3, 4],
                            [0, 5], [5, 6], [6, 7], [7, 8],
                            [0, 9], [9, 10], [10, 11], [11, 12],
                            [0, 13], [13, 14], [14, 15], [15, 16],
                            [0, 17], [17, 18], [18, 19], [19, 20],
                            [5, 9], [9, 13], [13, 17]
                        ]

                        ctx.lineWidth = 3
                        for (var c = 0; c < connections.length; c++) {
                            var start = connections[c][0]
                            var end = connections[c][1]
                            if (start < coords.length && end < coords.length) {
                                var c1 = colors[start]
                                var c2 = colors[end]
                                var r = (c1.r + c2.r) / 2
                                var g = (c1.g + c2.g) / 2
                                var b = (c1.b + c2.b) / 2
                                ctx.strokeStyle = Qt.rgba(r, g, b, 1)
                                ctx.beginPath()
                                ctx.moveTo(coords[start].x, coords[start].y)
                                ctx.lineTo(coords[end].x, coords[end].y)
                                ctx.stroke()
                            }
                        }

                        // Draw landmark points
                        for (var i = 0; i < 21; i++) {
                            if (i < coords.length) {
                                var color = colors[i]
                                ctx.fillStyle = Qt.rgba(color.r, color.g, color.b, color.a)
                                ctx.beginPath()
                                ctx.arc(coords[i].x, coords[i].y, 6, 0, 2 * Math.PI)
                                ctx.fill()
                                ctx.strokeStyle = "#000000"
                                ctx.lineWidth = 2
                                ctx.stroke()
                            }
                        }
                    }
                }
            }
        }
    }

    // Video output for camera feed
    VideoOutput {
        id: videoOutput
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectFit
        mirror: cameraView.mirror
        source: cameraView.frame
    }

    // Status banner overlay
    Rectangle {
        id: statusBanner
        visible: cameraView.statusText !== ""
        width: Math.min(cameraView.width - 32, cameraView.width * 0.9)
        height: 48
        radius: 12
        color: Qt.rgba(0, 0, 0, 0.7)
        x: (parent.width - width) / 2
        y: 16
        radius: 12
        clip: true

        Text {
            anchors.centerIn: parent
            text: cameraView.statusText
            color: cameraView.statusState === "error" ? "#F87171" :
                   cameraView.statusState === "success" ? "#4ADE80" :
                   cameraView.statusState === "warning" ? "#FBBF24" : "#22D3EE"
            font.family: "Inter, SF Pro Display, sans-serif"
            font.size: 14
            font.weight: 500
            wrapMode: Text.WordWrap
        }
    }

    // FPS counter
    Text {
        visible: cameraView.showFps && cameraView.fps > 0
        text: cameraView.fps.toFixed(1) + " FPS"
        x: 16
        y: 16
        color: "#71717A"
        font.family: "Inter, SF Pro Display, sans-serif"
        font.size: 12
        font.weight: 500
    }