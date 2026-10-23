import QtQuick 2.15
import QtQuick.Controls 2.15

import "../theme"

Item {
    id: statusBanner
    property string text: ""
    property string state: "info" // info, success, warning, error

    implicitWidth: 400
    implicitHeight: 48

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: theme.radiusButton
        color: state === "success" ? theme.colorSuccess() :
               state === "warning" ? theme.colorWarning() :
               state === "error" ? theme.colorError() : theme.colorSurface()
        border.color: state === "success" ? theme.colorSuccess() :
                      state === "warning" ? theme.colorWarning() :
                      state === "error" ? theme.colorError() : theme.colorBorder()
        border.width: 1
    }

    Text {
        anchors.centerIn: parent
        text: statusBanner.text
        font.family: theme.fontFamily
        font.pixelSize: theme.fontSizeBody
        color: state === "success" ? theme.colorSuccess() :
               state === "warning" ? theme.colorWarning() :
               state === "error" ? theme.colorError() : theme.colorTextPrimary()
    }
}