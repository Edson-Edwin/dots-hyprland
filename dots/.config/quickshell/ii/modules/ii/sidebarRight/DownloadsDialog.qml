import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.common
import qs.modules.common.widgets

WindowDialog {
    id: root
    backgroundHeight: 430
    property string period: ""
    property string feedback: ""
    function request(action, choice = "") {
        if (worker.running) return;
        const cmd = ["python3", Quickshell.shellPath("scripts/downloads-organizer/organizer.py"), action];
        if (choice) cmd.push(choice);
        worker.command = cmd;
        worker.running = true;
    }

    Process {
        id: worker
        stdout: SplitParser {
            onRead: line => {
                try {
                    const result = JSON.parse(line);
                    if (result.schedule !== undefined) root.period = result.schedule;
                    root.feedback = result.message;
                } catch (e) { root.feedback = Translation.tr("Couldn't read the organizer result."); }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: if (text.trim()) root.feedback = text.trim();
        }
    }
    Component.onCompleted: request("status")

    WindowDialogTitle { text: Translation.tr("Organize Downloads") }
    WindowDialogSeparator {}
    StyledText {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: Translation.tr("Sort loose files into folders by extension: for example, report.pdf goes into pdf/. Existing folders stay as they are.")
    }
    DialogButton {
        Layout.fillWidth: true
        buttonText: Translation.tr("Organize now")
        enabled: !worker.running
        onClicked: root.request("run")
    }
    StyledText {
        Layout.fillWidth: true
        text: Translation.tr("Automatic sorting")
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2
        Repeater {
            model: [{ label: Translation.tr("Off"), value: "off" },
                    { label: Translation.tr("Hourly"), value: "hourly" },
                    { label: Translation.tr("Daily"), value: "daily" },
                    { label: Translation.tr("Weekly"), value: "weekly" }]
            delegate: DialogButton {
                required property var modelData
                Layout.fillWidth: true
                enabled: !worker.running
                buttonText: (root.period === modelData.value ? "✓  " : "") + modelData.label
                onClicked: root.request("schedule", modelData.value)
            }
        }
    }
    StyledText {
        Layout.fillWidth: true
        Layout.fillHeight: true
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        elide: Text.ElideRight
        maximumLineCount: 3
        text: worker.running ? Translation.tr("Working…") : root.feedback
    }
    WindowDialogButtonRow {
        Item { Layout.fillWidth: true }
        DialogButton { buttonText: Translation.tr("Done"); onClicked: root.dismiss() }
    }
}
