import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root
    readonly property string sourceName: Quickshell.env("II_PRESENT_FROM")
    readonly property string targetName: Quickshell.env("II_PRESENT_TO")
    readonly property var source: Quickshell.screens.find(s => s.name === sourceName) ?? null
    readonly property var target: Quickshell.screens.find(s => s.name === targetName) ?? null
    property bool ready: false

    // Never fall back to showing the capture surface on its own source.
    Loader {
        active: root.source !== null && root.target !== null && root.source !== root.target
        sourceComponent: PanelWindow {
            id: panel
            screen: root.target
            anchors { left: true; right: true; top: true; bottom: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "ii-presentation-fill"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            color: "black"
            ScreencopyView {
                id: frame
                captureSource: root.source
                live: true
                paintCursor: true
                width: root.source?.width ?? 1
                height: root.source?.height ?? 1
                transform: Scale {
                    xScale: frame.parent.width / Math.max(1, frame.width)
                    yScale: frame.parent.height / Math.max(1, frame.height)
                }
                onHasContentChanged: root.ready = hasContent
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.BlankCursor
                // A presentation output is view-only. Keep the real pointer
                // on the laptop; the projected frame already includes it.
                onEntered: {
                    if (!root.source) return;
                    const x = root.source.x + Math.min(root.source.width - 8, Math.max(8, mouseX / width * root.source.width));
                    const y = root.source.y + Math.min(root.source.height - 8, Math.max(8, mouseY / height * root.source.height));
                    Quickshell.execDetached(["hyprctl","dispatch","hl.dsp.cursor.move({x=" + Math.round(x) + ",y=" + Math.round(y) + "})"]);
                }
            }
        }
    }
    Timer {
        interval: 300
        running: !root.source || !root.target || root.source === root.target
        onTriggered: Qt.quit()
    }
    IpcHandler {
        target: "projector"
        function status(): string { return root.ready ? "ready" : "starting" }
        function stop(): void { Qt.callLater(Qt.quit) }
    }
}
