import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../theme"

Item {
    id: screen
    property var pipeline: null
    property bool darkMode: true
    property string mode: "dictionary"
    property var entries: []
    property var questions: []
    property int questionIndex: 0
    property int score: 0
    property bool answered: false
    property string feedback: ""
    readonly property bool finished: questionIndex >= questions.length
    signal backRequested()
    signal practiceRequested(string signId)
    Theme { id: theme; isDark: screen.darkMode }
    function restartQuiz() {
        questions = pipeline.startQuiz()
        questionIndex = 0; score = 0; answered = false; feedback = ""
    }
    Component.onCompleted: {
        if (!pipeline) return
        if (mode === "quiz") restartQuiz()
        else entries = mode === "dictionary" ? pipeline.dictionarySigns() : pipeline.progressDetails()
    }
    Rectangle { anchors.fill: parent; color: theme.background() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 20
        RowLayout {
            Layout.fillWidth: true
            Button { text: "‹ Back"; onClicked: screen.backRequested() }
            Label {
                text: screen.mode === "dictionary" ? "Your sign library" : screen.mode === "progress" ? "Every practice counts" : "Quick knowledge quiz"
                color: theme.text(); font.pixelSize: 26; font.bold: true
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
        }
        Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: theme.textMuted()
            text: screen.mode === "dictionary" ? "Explore a sign, read the instructions, then practice at your own pace."
                  : screen.mode === "progress" ? "Lesson completion includes reviewed signs. Accuracy measures scored attempts only."
                  : "Match each description to a sign. This quiz tests knowledge, not camera recognition."
        }
        TextField {
            id: search; visible: screen.mode === "dictionary"; Layout.fillWidth: true
            placeholderText: "Search letters, numbers, or descriptions…"; Accessible.name: "Search signs"
        }
        Label {
            visible: screen.mode === "progress"
            text: pipeline ? pipeline.userStats.attempts + " practice records · " + pipeline.userStats.accuracy + "% scored accuracy · " + pipeline.userStats.streak + " day streak" : ""
            color: theme.accent(); font.pixelSize: 18
        }
        ListView {
            id: list; visible: screen.mode !== "quiz"
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 12
            model: screen.entries.filter(function(s) { return screen.mode !== "dictionary" || (s.label + " " + s.description).toLowerCase().indexOf(search.text.toLowerCase()) >= 0 })
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: list.width; height: row.implicitHeight + 32
                radius: 16; color: theme.surface(); border.color: theme.border()
                RowLayout {
                    id: row; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 20
                    Label { text: modelData.label; color: theme.accent(); font.pixelSize: 28; font.bold: true; Layout.preferredWidth: 100; wrapMode: Text.WordWrap }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: theme.text()
                            text: screen.mode === "dictionary" ? modelData.description : modelData.attempts + " practice records"
                        }
                        Label {
                            color: theme.textMuted()
                            text: screen.mode === "dictionary" ? modelData.category + " · " + (modelData.scored ? "Static sign" : "Self-guided") : modelData.accuracy + "% scored accuracy"
                        }
                    }
                    Button { visible: screen.mode === "dictionary"; text: "Practice ›"; onClicked: screen.practiceRequested(modelData.id) }
                }
            }
            Label {
                anchors.centerIn: parent; visible: list.count === 0; color: theme.textMuted()
                text: screen.mode === "progress" ? "Your progress starts with your first lesson." : "No matching signs. Try another search."
            }
        }
        Rectangle {
            visible: screen.mode === "quiz"; Layout.fillWidth: true; Layout.fillHeight: true
            color: theme.surface(); radius: 20; border.color: theme.border()
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 28; spacing: 20
                Label { color: theme.accent(); text: screen.finished ? "SESSION COMPLETE" : "QUESTION " + (screen.questionIndex + 1) + " OF " + screen.questions.length }
                Label {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap; color: theme.text(); font.pixelSize: 24
                    text: screen.finished ? "You scored " + screen.score + " / " + screen.questions.length : screen.questions[screen.questionIndex].prompt
                }
                Repeater {
                    model: screen.finished ? [] : screen.questions[screen.questionIndex].options
                    Button {
                        required property string modelData
                        Layout.fillWidth: true; Layout.preferredHeight: 48; text: modelData; enabled: !screen.answered
                        onClicked: {
                            var result = pipeline.answerQuiz(screen.questionIndex, modelData)
                            if (result.correct) screen.score++
                            screen.feedback = result.correct ? "Correct — well done." : "The answer is “" + result.answer + "”."
                            screen.answered = true
                        }
                    }
                }
                Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: screen.feedback; color: theme.accent(); font.pixelSize: 18 }
                Item { Layout.fillHeight: true }
                Button {
                    visible: screen.answered || screen.finished
                    text: screen.finished ? "Try a new quiz" : "Continue ›"; highlighted: true
                    onClicked: {
                        if (screen.finished) screen.restartQuiz()
                        else { screen.questionIndex++; screen.answered = false; screen.feedback = "" }
                    }
                }
            }
        }
    }
}
