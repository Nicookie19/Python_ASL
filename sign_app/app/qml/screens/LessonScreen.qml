import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Shapes 1.15

import "../components"
import "../theme/Theme"

Item {
    id: lessonScreen
    property var pipeline: null
    property var contentLoader: null
    property var cameraService: null

    property var currentModule: null
    property int currentSignIndex: 0
    property var signs: []
    property int attemptCount: 0
    property int successCount: 0
    property int holdStartTime: 0
    property int requiredHoldMs: 800

    signal goBack
    signal goNext
    signal goPrevious

    Component.onCompleted: {
        themeLoader.source = "theme/Theme.qml"
    }

    function prepare(moduleId, signIndex) {
        // Would be called from Python
    }

    function goBack() {
        mainWindow.showNavBar()
        pipeline.stop()
        pipeline.clearTarget()
        mainWindow._showScreen("home")
    }

    function goNext() {
        if (currentSignIndex < signs.length - 1) {
            currentSignIndex++
            loadCurrentSign()
        } else {
            completeModule()
        }
    }

    function goPrevious() {
        if (currentSignIndex > 0) {
            currentSignIndex--
            loadCurrentSign()
        }
    }

    function spaceAction() {
        if (nextButton.enabled) {
            goNext()
        }
    }

    function navigateRelative(delta) {
        if (delta > 0) goNext()
        else goPrevious()
    }

    function loadCurrentSign() {
        if (!signs || currentSignIndex >= signs.length) return

        var sign = signs[currentSignIndex]

        // Update UI
        targetLabel.text = sign.label

        // Check if motion sign (not scored)
        var isMotion = sign.metadata && sign.metadata.motion_sign
        if (isMotion) {
            targetLabel.text = sign.label
            statusBanner.text = "Watch & Learn: " + sign.label + " (motion sign)"
            statusBanner.state = "info"
            nextButton.enabled = true
        } else {
            statusBanner.text = "Show me: " + sign.label
            statusBanner.state = "info"
            nextButton.enabled = false
        }

        descriptionLabel.text = sign.description || "No description available."
        attemptLabel.text = "Attempts: " + attemptCount

        // Set reference landmarks if available
        if (sign.referenceLandmarks) {
            var landmarks = []
            for (var i = 0; i < sign.referenceLandmarks.length; i += 3) {
                landmarks.push({
                    x: sign.referenceLandmarks[i],
                    y: sign.referenceLandmarks[i + 1],
                    z: sign.referenceLandmarks[i + 2]
                })
            }
            referenceAnimation.landmarks = landmarks
            pipeline.setTargetSign(sign.id, landmarks)
        } else {
            pipeline.setTargetSign(sign.id, null)
        }

        updateProgressDots()
    }

    function buildProgressDots() {
        progressLayout.clear()
        for (var i = 0; i < signs.length; i++) {
            var dot = dotComponent.createObject(progressContainer, {
                "active": i < currentSignIndex,
                "current": i === currentSignIndex
            })
        }
    }

    function goNext() {
        if (currentSignIndex < signs.length - 1) {
            currentSignIndex++
            loadCurrentSign()
        } else {
            completeModule()
        }
    }

    function goPrevious() {
        if (currentSignIndex > 0) {
            currentSignIndex--
            loadCurrentSign()
        }
    }

    function completeModule() {
        // Would call Python to save progress
        mainWindow._showScreen("home")
    }

    function spaceAction() {
        if (nextButton.enabled) {
            goNext()
        }
    }

    function navigateRelative(delta) {
        if (delta > 0) goNext()
        else goPrevious()
    }

    Loader {
        id: themeLoader
        source: "theme/Theme.qml"
        onStatusChanged: {
            if (status === Loader.Ready) {
                lessonScreen.theme = item
            }
        }
    }

    Item {
        id: root
        property var pipeline: null
        property var contentLoader: null
        property var cameraService: null

        property var currentModule: null
        property int currentSignIndex: 0
        property var signs: []
        property int attemptCount: 0
        property int successCount: 0
        property int holdStartTime: 0
        property int requiredHoldMs: 800

        signal goBack
        signal goNext
        signal goPrevious

        HSplitView {
            id: mainSplit
            anchors.fill: parent

            // Left panel: Camera view (70%)
            Item {
                id: leftPanel
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 700
                Layout.minimumWidth: 500

                Column {
                    anchors.fill: parent
                    spacing: 12

                    // Status banner
                    StatusBanner {
                        id: statusBanner
                        text: "Loading lesson..."
                        state: "info"
                    }

                    // Camera view
                    CameraView {
                        id: cameraView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumWidth: 640
                        Layout.minimumHeight: 360
                        Layout.preferredWidth: 800
                        Layout.minimumHeight: 360
                    }

                    // Confidence meter
                    ConfidenceMeter {
                        id: confidenceMeter
                    }
                }
            }

            // Right panel: Reference (30%)
            Item {
                id: rightPanel
                Layout.preferredWidth: 360
                Layout.fillHeight: true

                Column {
                    anchors.fill: parent
                    spacing: 16

                    // Target letter display
                    Text {
                        id: targetLabel
                        text: "—"
                        font.family: theme.fontFamily
                        font.pixelSize: 96
                        font.weight: Font.Bold
                        horizontalAlignment: Qt.AlignHCenter
                        color: theme.colorTextPrimary()
                    }

                    // Reference animation
                    ReferenceAnimation {
                        id: referenceAnimation
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 280
                        Layout.preferredHeight: 300
                    }

                    // Description
                    Label {
                        id: descriptionLabel
                        text: ""
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeBase
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Qt.AlignTop
                    }

                    // Tips
                    Label {
                        id: tipsLabel
                        text: ""
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeSmall
                        color: theme.colorTextSecondary()
                        wrapMode: Text.WordWrap
                        visible: false
                    }

                    // Attempt counter
                    Label {
                        id: attemptLabel
                        text: "Attempts: 0"
                        font.family: theme.fontFamily
                        font.pixelSize: theme.fontSizeCaption
                        horizontalAlignment: Qt.AlignHCenter
                        color: theme.colorTextSecondary()
                    }

                    // Progress dots
                    Row {
                        id: progressContainer
                        spacing: 8
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    // Navigation buttons
                    Row {
                        spacing: 12

                        Button {
                            text: "← Back"
                            onClicked: goPrevious()
                            enabled: currentSignIndex > 0
                        }

                        Button {
                            text: "Skip"
                            flat: true
                            onClicked: goNext()
                        }

                        Button {
                            id: nextButton
                            text: "Next →"
                            enabled: false
                            onClicked: goNext()
                        }
                    }
                }
            }
        }
    }

    Component {
        id: dotComponent
        Item {
            property bool active: false
            property bool current: false
            width: 12
            height: 12

            Rectangle {
                anchors.fill: parent
                radius: 6
                color: current ? theme.colorAccent() :
                         active ? theme.colorSuccess() : theme.colorSurfaceVariant()
            }
        }
    }