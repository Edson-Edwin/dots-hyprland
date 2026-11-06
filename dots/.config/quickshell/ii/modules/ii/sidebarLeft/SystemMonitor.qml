import qs.modules.common
import qs.modules.common.widgets
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

Item {
    id: root
    property bool active: false
    property int page: 0
    property bool sortMemory: false
    property string query: ""
    property var stats: ({})
    property string error: ""
    property var cpuHistory: []
    property var ramHistory: []
    property var swapHistory: []
    property var rxHistory: []
    property var txHistory: []
    property var readHistory: []
    property var writeHistory: []
    readonly property var processRows: {
        const q=query.toLowerCase();
        return (stats.processes ?? []).filter(p => !q || p.name.toLowerCase().includes(q) || String(p.pid).includes(q))
            .sort((a,b) => sortMemory ? b.rss-a.rss : b.cpu-a.cpu || b.rss-a.rss).slice(0,60);
    }
    readonly property var portRows: (stats.ports ?? []).filter(p => !query || (p.address+" "+p.owner+" "+p.protocol).toLowerCase().includes(query.toLowerCase()))
    function bytes(v) {
        v=Number(v)||0;
        const units=["B","KiB","MiB","GiB","TiB"];let i=0;
        while (v>=1024 && i<4) { v/=1024;++i; }
        return v.toFixed(i>1 ? 1 : 0)+" "+units[i];
    }
    function percent(v) { return (Number(v)||0).toFixed(1)+"%"; }
    function history(old,value) { return old.concat([Number(value)||0]).slice(-60); }
    function peak(a,b) { return Math.max(1024,...a,...b)*1.15; }
    function receive(text) {
        try {
            const next=JSON.parse(text);
            if (next.error) { error=next.error;return; }
            stats=next;error="";
            cpuHistory=history(cpuHistory,next.cpu);ramHistory=history(ramHistory,next.ram_percent);swapHistory=history(swapHistory,next.swap_percent);
            rxHistory=history(rxHistory,next.rx);txHistory=history(txHistory,next.tx);
            readHistory=history(readHistory,next.disk_read);writeHistory=history(writeHistory,next.disk_write);
        } catch (_) { error="Unable to read system metrics"; }
    }
    onActiveChanged: {
        if (active) {
            cpuHistory=[];ramHistory=[];swapHistory=[];rxHistory=[];txHistory=[];readHistory=[];writeHistory=[];
            error="";
        }
    }
    Process {
        id: collector
        command: ["/usr/bin/python3", "-u", Quickshell.shellPath("scripts/system-monitor/collect.py")]
        running: root.active
        stdout: SplitParser { onRead: data => root.receive(data) }
        stderr: StdioCollector {}
        onExited: (code,status) => { if (root.active && code!==0) root.error="Monitor stopped. Reopen this tab to retry."; }
    }
    component Label: StyledText { textFormat: Text.PlainText; font.pixelSize: 12; color: Appearance.colors.colSubtext }
    component Action: Button {
        id: button
        property bool selected: false
        implicitHeight: 34
        padding: 10
        contentItem: StyledText { text: button.text; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: button.selected ? Appearance.colors.colOnPrimary : Appearance.colors.colOnLayer1 }
        background: Rectangle { radius: 17; color: button.selected ? Appearance.colors.colPrimary : button.hovered ? Appearance.colors.colLayer3 : Appearance.colors.colLayer2 }
    }
    component Panel: Rectangle { radius: 18; color: Appearance.colors.colLayer2; Layout.fillWidth: true }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2;Layout.fillWidth: true
                StyledText { text: "System monitor"; font.pixelSize: 22; font.weight: Font.DemiBold }
                Label { text: root.stats.uptime !== undefined ? Math.floor(root.stats.uptime/3600)+"h "+Math.floor(root.stats.uptime%3600/60)+"m uptime · "+root.stats.process_count+" processes" : "Reading your system…" }
            }
            Rectangle { width: 7;height: 7;radius: 4;color: root.error ? Appearance.colors.colError : Appearance.colors.colPrimary }
            Label { text: root.error ? "ERROR" : root.active ? "LIVE" : "PAUSED";font.pixelSize: 10 }
        }
        RowLayout {
            Layout.fillWidth: true;spacing: 6
            Repeater {
                model: ["Overview","Processes","Ports"]
                Action { required property int index;required property string modelData;Layout.fillWidth: true;text: modelData;selected: root.page===index;onClicked: {root.page=index;search.clear();} }
            }
        }
        Label { visible: root.error!=="";text: root.error;wrapMode: Text.Wrap;Layout.fillWidth: true;color: Appearance.colors.colError }
        TextField {
            id: search
            visible: root.page!==0;Layout.fillWidth: true;implicitHeight: 38
            placeholderText: root.page===1 ? "Find process or PID…" : "Find port, address or process…"
            color: Appearance.colors.colOnLayer1;placeholderTextColor: Appearance.colors.colSubtext
            onTextChanged: root.query=text
            background: Rectangle { color: Appearance.colors.colLayer2;radius: 12 }
        }
        RowLayout {
            visible: root.page===1;Layout.fillWidth: true
            Action { text: "CPU ↓";selected: !root.sortMemory;onClicked: root.sortMemory=false }
            Action { text: "Memory ↓";selected: root.sortMemory;onClicked: root.sortMemory=true }
            Label { Layout.fillWidth: true;horizontalAlignment: Text.AlignRight;text: root.processRows.length+" shown" }
        }
        Label {
            visible: root.page!==0;Layout.fillWidth: true;wrapMode: Text.Wrap;font.pixelSize: 11
            text: root.page===1 ? "Top processes · CPU: 100% = one core · RAM: RSS" : "TCP listeners / UDP sockets · local bindings, not an internet scan"
        }
        StyledFlickable {
            id: overview
            visible: root.page===0
            Layout.fillWidth: true;Layout.fillHeight: true
            clip: true;contentHeight: overviewColumn.implicitHeight
            ColumnLayout {
                id: overviewColumn;width: overview.width;spacing: 10
                MonitorMetric { Layout.fillWidth: true; title: "CPU ACTIVITY";value: root.percent(root.stats.cpu);detail: "Load average  "+(root.stats.load ?? []).map(v => v.toFixed(2)).join("  ·  ");history: root.cpuHistory;implicitHeight: 155 }
                GridLayout {
                    Layout.fillWidth: true;columns: 2;columnSpacing: 10
                    MonitorMetric { Layout.fillWidth: true;title: "MEMORY";value: root.percent(root.stats.ram_percent);detail: root.bytes(root.stats.ram_used)+" / "+root.bytes(root.stats.ram_total);history: root.ramHistory;accent: Appearance.colors.colSecondary }
                    MonitorMetric { Layout.fillWidth: true;title: "SWAP";value: root.percent(root.stats.swap_percent);detail: root.bytes(root.stats.swap_used)+" / "+root.bytes(root.stats.swap_total);history: root.swapHistory;accent: Appearance.colors.colTertiary }
                }
                Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "Available "+root.bytes(root.stats.ram_available)+" · Cache "+root.bytes(root.stats.ram_cache)+"\nCompressed swap occupies "+root.bytes(root.stats.zram)+" RAM";font.pixelSize: 11 }
                Panel {
                    implicitHeight: coreColumn.implicitHeight+28
                    ColumnLayout {
                        id: coreColumn;anchors { left: parent.left;right: parent.right;top: parent.top;margins: 14 }spacing: 8
                        Label { text: "LOGICAL CPU CORES" }
                        GridLayout {
                            Layout.fillWidth: true;columns: 4;rowSpacing: 6;columnSpacing: 6
                            Repeater {
                                model: root.stats.cores ?? []
                                Rectangle {
                                    required property int index;required property real modelData
                                    Layout.fillWidth: true;implicitHeight: 24;radius: 5;color: Appearance.colors.colLayer3;clip: true
                                    Rectangle { height: parent.height;width: parent.width*Math.min(1,modelData/100);radius: 5;color: Qt.alpha(Appearance.colors.colPrimary,.35) }
                                    Label { anchors.centerIn: parent;text: (index+1)+"  "+Math.round(modelData)+"%";font.pixelSize: 10;color: Appearance.colors.colOnLayer1 }
                                }
                            }
                        }
                    }
                }
                Panel {
                    implicitHeight: 148
                    ColumnLayout {
                        anchors.fill: parent;anchors.margins: 14;spacing: 6
                        RowLayout { Layout.fillWidth: true;Label { text: "NETWORK" }Label { Layout.fillWidth: true;horizontalAlignment: Text.AlignRight;text: (root.stats.interfaces ?? []).join(", ");elide: Text.ElideRight } }
                        RowLayout { Label { text: "↓ "+root.bytes(root.stats.rx)+"/s";color: Appearance.colors.colPrimary }Item { Layout.fillWidth: true }Label { text: "↑ "+root.bytes(root.stats.tx)+"/s";color: Appearance.colors.colTertiary } }
                        MonitorChart { Layout.fillWidth: true;Layout.fillHeight: true;values: root.rxHistory;secondaryValues: root.txHistory;ceiling: root.peak(values,secondaryValues) }
                    }
                }
                Panel {
                    implicitHeight: 148
                    ColumnLayout {
                        anchors.fill: parent;anchors.margins: 14;spacing: 6
                        Label { text: "DISK ACTIVITY" }
                        RowLayout { Label { text: "Read "+root.bytes(root.stats.disk_read)+"/s";color: Appearance.colors.colPrimary }Item { Layout.fillWidth: true }Label { text: "Write "+root.bytes(root.stats.disk_write)+"/s";color: Appearance.colors.colTertiary } }
                        MonitorChart { Layout.fillWidth: true;Layout.fillHeight: true;values: root.readHistory;secondaryValues: root.writeHistory;ceiling: root.peak(values,secondaryValues) }
                    }
                }
                Repeater {
                    model: root.stats.disks ?? []
                    Panel {
                        required property var modelData
                        implicitHeight: 66
                        ColumnLayout {
                            anchors.fill: parent;anchors.margins: 12;spacing: 8
                            Label { text: modelData.mount+"   "+root.bytes(modelData.used)+" / "+root.bytes(modelData.total)+"   ·   "+root.percent(modelData.percent);Layout.fillWidth: true;elide: Text.ElideRight }
                            Rectangle { Layout.fillWidth: true;implicitHeight: 5;radius: 3;color: Appearance.colors.colLayer3
                                Rectangle { height: parent.height;width: parent.width*modelData.percent/100;radius: 3;color: Appearance.colors.colSecondary }
                            }
                        }
                    }
                }
                Panel {
                    visible: (root.stats.temperatures ?? []).length>0
                    implicitHeight: sensorColumn.implicitHeight+24
                    ColumnLayout {
                        id: sensorColumn;anchors { left: parent.left;right: parent.right;top: parent.top;margins: 12 }spacing: 6
                        Label { text: "TEMPERATURES" }
                        Repeater { model: root.stats.temperatures ?? [];Label { required property var modelData;text: modelData.label+"   "+modelData.value+" °C";Layout.fillWidth: true;elide: Text.ElideRight } }
                    }
                }
                Label { text: "2-second samples · 2-minute graphs · pauses when closed";font.pixelSize: 10;Layout.fillWidth: true;wrapMode: Text.Wrap }
            }
        }
        ListView {
            visible: root.page===1;Layout.fillWidth: true;Layout.fillHeight: true;clip: true;spacing: 6
            model: root.processRows
            ScrollBar.vertical: StyledScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width;height: 66;radius: 12;color: Appearance.colors.colLayer2
                ColumnLayout {
                    anchors.fill: parent;anchors.margins: 10;spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        StyledText { textFormat: Text.PlainText;text: modelData.name;font.pixelSize: 13;Layout.fillWidth: true;elide: Text.ElideRight }
                        StyledText { text: root.percent(modelData.cpu);color: Appearance.colors.colPrimary;font.pixelSize: 13 }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "PID "+modelData.pid+" · "+modelData.state;Layout.fillWidth: true;elide: Text.ElideRight;font.pixelSize: 11 }
                        Label { text: root.bytes(modelData.rss);font.pixelSize: 11 }
                    }
                }
            }
            Label { anchors.centerIn: parent;visible: parent.count===0;text: "No matching processes" }
        }
        ListView {
            visible: root.page===2;Layout.fillWidth: true;Layout.fillHeight: true;clip: true;spacing: 6
            model: root.portRows
            ScrollBar.vertical: StyledScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width;height: 70;radius: 12;color: Appearance.colors.colLayer2
                ColumnLayout {
                    anchors.fill: parent;anchors.margins: 10;spacing: 5
                    RowLayout { Layout.fillWidth: true
                        Label { text: modelData.protocol;color: Appearance.colors.colPrimary;font.weight: Font.Bold }
                        StyledText { textFormat: Text.PlainText;text: modelData.address;font.pixelSize: 13;Layout.fillWidth: true;elide: Text.ElideMiddle }
                    }
                    Label { text: modelData.owner;Layout.fillWidth: true;elide: Text.ElideRight;font.pixelSize: 11 }
                }
            }
            Label { anchors.centerIn: parent;visible: parent.count===0;text: root.stats.port_error || "No matching listening sockets";width: parent.width;wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter }
        }
    }
}
