import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.common
import qs.modules.common.widgets

RippleButton {
    id: root
    property string voiceState: "idle"
    readonly property string helper: Quickshell.env("HOME") + "/.config/hypr/hyprland/scripts/edson/ii-voice-ai.sh"
    readonly property bool recording: voiceState === "recording"
    implicitWidth: 34
    implicitHeight: 30
    buttonRadius: Appearance.rounding.full
    colBackground: recording ? Appearance.m3colors.m3errorContainer : "transparent"
    colBackgroundHover: Appearance.colors.colLayer1Hover
    colRipple: Appearance.colors.colLayer1Active

    onPressed: Quickshell.execDetached([root.helper, root.recording ? "dictate" : "menu"])
    MaterialSymbol {
        anchors.centerIn: parent
        text: root.recording ? "stop_circle" : root.voiceState === "transcribing" ? "hourglass_top" : "mic"
        iconSize: 21
        color: root.recording ? Appearance.m3colors.m3onErrorContainer : Appearance.barForeground(Appearance.colors.colOnLayer0)
    }
    StyledToolTip {
        text: root.recording ? "Stop dictation · Ctrl + Super + D" : "Voice & Chat · Dictate: Ctrl + Super + D · Chat: Ctrl + Super + A"
    }
    Process {
        running: true
        command: [root.helper, "init"]
        onExited: statusFile.path = Quickshell.env("XDG_RUNTIME_DIR") + "/ii-voice-ai/status.json"
    }
    FileView {
        id: statusFile
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try { root.voiceState = JSON.parse(text()).state || "idle"; }
            catch (error) { root.voiceState = "idle"; }
        }
    }
}
