import QtQuick 2.15
import QtQuick.Controls 2.15

import "../theme"

Item {
    id: confidenceMeter
    property real value: 0 // 0-1
    property real threshold: 0.7
    property bool active: false

    implicitWidth: 200
    implicitHeight: 24

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: 12
        color: theme.colorSurface()
        border.color: theme.colorBorder()
        border.width: 1
    }

    Rectangle {
        id: fill
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: confidenceMeter.value * parent.width
        radius: 12
        color: confidenceMeter.value >= confidenceMeter.threshold ? theme.colorSuccess() : theme.colorAccent()
        Behavior on width { NumberAnimation { duration: 100 } }
    }

    // Threshold marker
    Rectangle {
        id: thresholdMarker
        x: confidenceMeter.threshold * parent.width - 1
        y: 0
        width: 2
        height: parent.height
        color: theme.colorTextSecondary()
        visible: confidenceMeter.active
    }

    Text {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 8
        text: Math.round(confidenceMeter.value * 100) + "%"
        font.family: theme.fontFamily
        font.pixelSize: theme.fontSizeSmall
        color: theme.colorTextSecondary()
    }
}