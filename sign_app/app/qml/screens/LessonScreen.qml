import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

import "../components"
import "../theme"

Item {
    id: lessonScreen

    property var pipeline: null
    property var contentLoader: null
    property var cameraService: null
    property bool darkMode: true
    property var currentModule: null
    property int currentSignIndex: 0
    property var signs: []
    property int attemptCount: 0
    property int successCount: 0
    property int requiredHoldMs: 800
    property bool isCorrect: false
    property bool lessonComplete: false
    property int holdStartedAt: 0
    property var pipelineResult: null
    property string cameraImageSource: ""
    property string statusText: "Choose a sign to begin"
    property string statusState: "info"

    readonly property var sampleSigns: [
        { "id": "asl_a", "label": "A", "difficulty": "Starter", "description": "Close your fingers into a fist and rest your thumb along the side of your index finger.", "tip": "Keep your knuckles facing the camera." },
        { "id": "asl_b", "label": "B", "difficulty": "Starter", "description": "Hold all four fingers together and upright, with your thumb folded across the palm.", "tip": "Keep the fingers straight and touching." },
        { "id": "asl_c", "label": "C", "difficulty": "Starter", "description": "Curve your fingers and thumb to make a relaxed C shape.", "tip": "Leave a clear space between fingertips." }
    ]
    readonly property var activeSigns: signs && signs.length ? signs : sampleSigns
    readonly property var currentSign: activeSigns.length > 0
                                       ? activeSigns[Math.min(currentSignIndex, activeSigns.length - 1)] : null
    readonly property real lessonProgress: activeSigns.length > 0
                                           ? (currentSignIndex + 1) / activeSigns.length : 0

    signal backRequested()
    signal nextRequested(int signIndex)
    signal previousRequested(int signIndex)

    Theme { id: theme; isDark: lessonScreen.darkMode }

    function callPipeline(name, first, second) {
        if (!pipeline || !pipeline[name]) return
        if (second !== undefined) pipeline[name](first, second)
        else if (first !== undefined) pipeline[name](first)
        else pipeline[name]()
    }

    function prepare(moduleId, signIndex) {
        if (typeof bridge !== "undefined" && bridge && bridge.lessonSigns) {
            var loadedSigns = bridge.lessonSigns(moduleId)
            if (loadedSigns && loadedSigns.length)
                signs = loadedSigns
            if (bridge.moduleInfo)
                currentModule = bridge.moduleInfo(moduleId)
        }
        currentSignIndex = Math.max(0, signIndex || 0)
        attemptCount = 0
        successCount = 0
        lessonComplete = false
        applyCurrentSign()
    }

    function applyCurrentSign() {
        if (!currentSign) return
        isCorrect = false
        holdStartedAt = 0
        holdTimer.stop()
        statusText = "Show the sign for “" + currentSign.label + "”"
        statusState = "info"
        // The backend accepts null reference landmarks, which keeps this
        // screen usable with content packs that only provide descriptions.
        if (typeof bridge !== "undefined" && bridge && bridge.startPractice)
            bridge.startPractice(currentSign.id)
        else
            callPipeline("setTargetSign", currentSign.id, null)
    }

    function goBack() {
        if (typeof bridge !== "undefined" && bridge && bridge.stopPractice)
            bridge.stopPractice()
        else {
            callPipeline("stop")
            callPipeline("clearTarget")
        }
        backRequested()
    }

    function goPrevious() {
        if (currentSignIndex <= 0) return
        currentSignIndex--
        applyCurrentSign()
        previousRequested(currentSignIndex)
    }

    function goNext() {
        if (currentSignIndex >= activeSigns.length - 1) {
            lessonComplete = true
            statusText = "Lesson complete — excellent work!"
            statusState = "success"
            return
        }
        currentSignIndex++
        applyCurrentSign()
        nextRequested(currentSignIndex)
    }

    function handleInferenceResult(result) {
        pipelineResult = result
        if (!result || !currentSign || !result.recognition) return

        var predicted = result.recognition.label || ""
        var confidence = result.recognition.confidence || 0
        var reliable = result.recognition.is_reliable === undefined
                       ? confidence >= 0.65 : result.recognition.is_reliable
        if (predicted.toUpperCase() === currentSign.label.toUpperCase() && reliable) {
            if (!isCorrect) {
                isCorrect = true
                holdStartedAt = Date.now()
                statusText = "Great shape — hold it steady"
                statusState = "success"
                holdTimer.start()
            }
        } else if (isCorrect) {
            isCorrect = false
            holdTimer.stop()
            attemptCount++
            statusText = "Almost there — reset and try “" + currentSign.label + "”"
            statusState = "warning"
        }
    }

    Timer {
        id: holdTimer
        interval: 40
        repeat: true
        onTriggered: {
            if (!lessonScreen.isCorrect) {
                stop()
                return
            }
            if (Date.now() - lessonScreen.holdStartedAt >= lessonScreen.requiredHoldMs) {
                stop()
                lessonScreen.isCorrect = false
                lessonScreen.successCount++
                lessonScreen.attemptCount++
                lessonScreen.statusText = "Perfect — “" + lessonScreen.currentSign.label + "” is complete"
                lessonScreen.statusState = "success"
            }
        }
    }

    Connections {
        // `bridge` is supplied by app/qml/main.py when this screen is hosted
        // by the QML app. Keeping the target null makes design previews safe.
        target: typeof bridge === "undefined" || !bridge ? null : bridge
        function onInferenceResultReady(result) {
            lessonScreen.handleInferenceResult(result)
        }
        function onStatusChanged(message, state) {
            lessonScreen.statusText = message
            lessonScreen.statusState = state
        }
    }

    Rectangle {
        anchors.fill: parent
        color: theme.background()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: theme.space5
        spacing: theme.space5

        RowLayout {
            Layout.fillWidth: true
            spacing: theme.space4

            Button {
                id: lessonBackButton
                text: "‹  Lessons"
                Layout.preferredHeight: 42
                padding: theme.space4
                onClicked: lessonScreen.goBack()
                background: Rectangle {
                    radius: theme.radiusSm
                    color: lessonBackButton.down ? theme.surfaceMuted() : theme.surface()
                    border.color: theme.border()
                }
                contentItem: Text {
                    text: lessonBackButton.text
                    color: theme.text()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textSm
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: currentModule && (currentModule.title || currentModule.name)
                          ? (currentModule.title || currentModule.name) : "Fingerspelling practice"
                    color: theme.text()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textXl
                    font.weight: Font.DemiBold
                }
                Text {
                    text: "Sign " + (currentSignIndex + 1) + " of " + activeSigns.length + "  •  Practice at your pace"
                    color: theme.textMuted()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textSm
                }
            }

            ProgressRing {
                Layout.preferredWidth: 48
                Layout.preferredHeight: 48
                progress: lessonProgress
                lineWidth: 5
                ringColor: theme.accent()
                trackColor: theme.surfaceMuted()
                Text {
                    anchors.centerIn: parent
                    text: Math.round(lessonProgress * 100) + "%"
                    color: theme.text()
                    font.family: theme.fontFamily
                    font.pixelSize: theme.textXs
                    font.weight: Font.DemiBold
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: width >= 980 ? 2 : 1
            columnSpacing: theme.space5
            rowSpacing: theme.space5

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 360
                Layout.preferredWidth: width >= 980 ? 700 : -1
                radius: theme.radiusLg
                color: theme.surface()
                border.color: theme.border()

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space4
                    spacing: theme.space3

                    CameraView {
                        id: cameraView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        imageSource: lessonScreen.cameraImageSource
                        hands: pipelineResult && pipelineResult.hands ? pipelineResult.hands : []
                        targetLandmarks: pipelineResult ? pipelineResult.target_landmarks : null
                        darkMode: lessonScreen.darkMode
                        statusText: lessonScreen.statusText
                        statusState: lessonScreen.statusState
                        cameraName: cameraService && cameraService.get_active_device
                                    ? "Live camera" : "Camera preview"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: pipelineResult && pipelineResult.confidence_meter
                                  ? "Recognition confidence"
                                  : "Tracker is ready"
                            color: theme.textMuted()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: pipelineResult && pipelineResult.confidence_meter
                                  ? Math.round((pipelineResult.confidence_meter[1] || 0) * 100) + "%"
                                  : "Waiting for hand"
                            color: pipelineResult && pipelineResult.hands && pipelineResult.hands.length
                                   ? theme.success() : theme.textMuted()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 360
                Layout.preferredWidth: width >= 980 ? 360 : -1
                radius: theme.radiusLg
                color: theme.surface()
                border.color: theme.border()

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: theme.space5
                    spacing: theme.space4

                    RowLayout {
                        Layout.fillWidth: true
                        Rectangle {
                            width: difficulty.implicitWidth + theme.space3 * 2
                            height: 28
                            radius: height / 2
                            color: theme.accentSoft()
                            Text {
                                id: difficulty
                                anchors.centerIn: parent
                                text: currentSign && currentSign.difficulty ? currentSign.difficulty : "Practice"
                                color: theme.accent()
                                font.family: theme.fontFamily
                                font.pixelSize: theme.textXs
                                font.weight: Font.DemiBold
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "Attempts " + attemptCount
                            color: theme.textMuted()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textXs
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 220
                        radius: theme.radiusMd
                        color: theme.surfaceRaised()
                        border.color: theme.border()

                        ReferenceFigure {
                            anchors.centerIn: parent
                            targetLandmarks: pipelineResult ? pipelineResult.target_landmarks : null
                            darkMode: lessonScreen.darkMode
                            label: currentSign ? currentSign.label : ""
                            mirror: cameraView.mirror
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "How to make it"
                        color: theme.text()
                        font.family: theme.fontFamily
                        font.pixelSize: theme.textLg
                        font.weight: Font.DemiBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: currentSign && currentSign.description ? currentSign.description : "Choose a sign to see its instructions."
                        color: theme.textMuted()
                        font.family: theme.fontFamily
                        font.pixelSize: theme.textMd
                        lineHeight: 1.35
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: tipText.implicitHeight + theme.space4 * 2
                        radius: theme.radiusMd
                        color: theme.warningSoft()
                        Text {
                            id: tipText
                            anchors.fill: parent
                            anchors.margins: theme.space3
                            text: "Tip  ·  " + (currentSign && currentSign.tip ? currentSign.tip : "Relax your shoulders and keep your hand well lit.")
                            color: theme.warning()
                            font.family: theme.fontFamily
                            font.pixelSize: theme.textSm
                            wrapMode: Text.WordWrap
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Item { Layout.fillHeight: true }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: theme.space3
                        Button {
                            id: previousButton
                            text: "‹ Previous"
                            enabled: currentSignIndex > 0
                            Layout.preferredHeight: 48
                            onClicked: lessonScreen.goPrevious()
                            background: Rectangle {
                                radius: theme.radiusSm
                                color: parent.enabled ? theme.surfaceRaised() : theme.surfaceMuted()
                                border.color: theme.border()
                            }
                            contentItem: Text {
                                text: previousButton.text; color: previousButton.enabled ? theme.text() : theme.textFaint()
                                font.family: theme.fontFamily; font.pixelSize: theme.textSm
                                font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            }
                        }
                        Button {
                            id: nextButton
                            Layout.fillWidth: true
                            text: lessonComplete ? "Back to lessons" : currentSignIndex === activeSigns.length - 1 ? "Finish lesson" : "Next sign  ›"
                            Layout.preferredHeight: 48
                            onClicked: lessonComplete ? lessonScreen.goBack() : lessonScreen.goNext()
                            background: Rectangle {
                                radius: theme.radiusSm
                                color: nextButton.down ? theme.accentStrong() : theme.accent()
                            }
                            contentItem: Text {
                                text: nextButton.text; color: "#06212B"; font.family: theme.fontFamily
                                font.pixelSize: theme.textSm; font.weight: Font.Bold
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }
        }

        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: theme.space2
            Repeater {
                model: activeSigns.length
                delegate: Rectangle {
                    width: index === currentSignIndex ? 28 : 8
                    height: 8
                    radius: 4
                    color: index < currentSignIndex ? theme.success()
                           : index === currentSignIndex ? theme.accent() : theme.surfaceMuted()
                    Behavior on width { NumberAnimation { duration: 150 } }
                }
            }
        }
    }

}
