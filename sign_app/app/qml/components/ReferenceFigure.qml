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
    property string imageSource: ""
    property string status: ""
    property string statusState: "info"
    property real holdProgress: 0

    Theme { id: theme; isDark: referenceFigure.darkMode }

    // Fallback: draws a simple letter card when no image is available
    function fallbackSource() {
        return ""
    }

    Rectangle {
        id: cardBackground
        anchors.fill: parent
        radius: theme.radiusMd
        color: theme.surface()
        border.color: theme.border()
        border.width: 1
    }

    Image {
        id: signImage
        anchors.fill: parent
        anchors.margins: theme.space2
        source: referenceFigure.imageSource
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: true
        sourceSize.width: 512
        sourceSize.height: 512

        // Fallback to letter card if image fails to load
        onStatusChanged: {
            if (signImage.status === Image.Error || signImage.status === Image.Null) {
                letterCard.visible = true
                signImage.visible = false
                console.warn("ReferenceFigure: Failed to load image for", referenceFigure.label, "- using fallback")
            } else if (signImage.status === Image.Ready) {
                letterCard.visible = false
                signImage.visible = true
            }
        }
    }

    // Fallback letter card - shown when image is missing or fails to load
    Rectangle {
        id: letterCard
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.7
        height: width
        radius: theme.radiusMd
        color: theme.accentSoft()
        border.color: theme.accent()
        border.width: 2
        visible: !signImage.source || signImage.status === Image.Error || signImage.status === Image.Null

        Text {
            anchors.centerIn: parent
            text: referenceFigure.label ? referenceFigure.label : "?"
            color: theme.accent()
            font.family: theme.fontFamily
            font.pixelSize: width * 0.5
            font.weight: Font.Bold
        }
    }

    // Motion sign badge
    Rectangle {
        id: motionBadge
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: theme.space2
        width: 70
        height: 24
        radius: height / 2
        color: theme.warning()
        visible: referenceFigure.status === "motion" || referenceFigure.label === "J" || referenceFigure.label === "Z"
        Text {
            anchors.centerIn: parent
            text: "Motion"
            color: "#06212B"
            font.family: theme.fontFamily
            font.pixelSize: theme.textXs
            font.weight: Font.DemiBold
            padding: theme.space2
        }
    }

    // Hold progress ring (shows when evaluating)
    Rectangle {
        id: holdRing
        anchors.centerIn: parent
        width: parent.width * 0.85
        height: width
        visible: referenceFigure.status === "evaluating" || referenceFigure.status === "hold"
        Canvas {
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var centerX = width / 2
                var centerY = height / 2
                var radius = Math.min(width, height) / 2 - 4
                // Background ring
                ctx.lineWidth = 6
                ctx.strokeStyle = theme.surfaceMuted()
                ctx.beginPath()
                ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
                ctx.stroke()
                // Progress ring
                if (referenceFigure.holdProgress !== undefined) {
                    ctx.strokeStyle = theme.accent()
                    ctx.lineCap = "round"
                    ctx.beginPath()
                    ctx.arc(centerX, centerY, radius, -Math.PI/2, -Math.PI/2 + Math.PI * 2 * referenceFigure.holdProgress)
                    ctx.stroke()
                }
            }
        }
    }

    // Status indicator (correct/wrong/evaluating)
    Rectangle {
        id: statusIndicator
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width, statusLabel.implicitWidth + 16)
        height: 28
        radius: height / 2
        color: theme.stateSurface(referenceFigure.statusState)
        border.width: 1
        border.color: theme.stateColor(referenceFigure.statusState)
        visible: referenceFigure.status.length > 0

        Text {
            anchors.centerIn: parent
            padding: theme.space2
            id: statusLabel
            text: referenceFigure.status
            color: theme.stateColor(referenceFigure.statusState)
            font.family: theme.fontFamily
            font.pixelSize: theme.textSm
            font.weight: Font.Medium
        }
    }

    // Label at bottom
    Text {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        visible: !referenceFigure.imageSource && !referenceFigure.status
        text: referenceFigure.label ? referenceFigure.label : "Reference"
        color: theme.textMuted()
        font.family: theme.fontFamily
        font.pixelSize: 14
        font.weight: Font.Medium
    }

    onImageSourceChanged: {
        signImage.source = referenceFigure.imageSource
    }
}