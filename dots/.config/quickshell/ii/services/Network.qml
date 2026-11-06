pragma Singleton
pragma ComponentBehavior: Bound

// Took many bits from https://github.com/caelestia-dots/shell (GPLv3)

import Quickshell
import Quickshell.Io
import QtQuick
import qs.services.network
import "network/NmcliParser.js" as NmcliParser

/**
 * Network service with nmcli.
 */
Singleton {
    id: root

    property bool wifi: true
    property bool ethernet: false

    property bool wifiEnabled: false
    readonly property bool wifiScanning: rescanProcess.running
    property string wifiScanError: ""
    property string wifiLastScan: ""
    property int scanRevision: 0
    property bool wifiConnecting: connectProc.running
    property WifiAccessPoint wifiConnectTarget
    property list<WifiAccessPoint> wifiNetworks: []
    readonly property WifiAccessPoint active: wifiNetworks.find(n => n.active) ?? null
    readonly property list<var> friendlyWifiNetworks: [...wifiNetworks].sort((a, b) => {
        if (a.active && !b.active)
            return -1;
        if (!a.active && b.active)
            return 1;
        return b.strength - a.strength;
    })
    property string wifiStatus: "disconnected"

    property string networkName: ""
    property int networkStrength
    property string materialSymbol: root.ethernet
        ? "lan"
        : (root.wifiEnabled && root.wifiStatus === "connected")
            ? (
                (root.active?.strength ?? 0) > 83 ? "signal_wifi_4_bar" :
                (root.active?.strength ?? 0) > 67 ? "network_wifi" :
                (root.active?.strength ?? 0) > 50 ? "network_wifi_3_bar" :
                (root.active?.strength ?? 0) > 33 ? "network_wifi_2_bar" :
                (root.active?.strength ?? 0) > 17 ? "network_wifi_1_bar" :
                "signal_wifi_0_bar"
            )
            : (root.wifiStatus === "connecting")
                ? "signal_wifi_statusbar_not_connected"
                : (root.wifiStatus === "disconnected")
                    ? "wifi_find"
                    : (root.wifiStatus === "disabled")
                        ? "signal_wifi_off"
                        : "signal_wifi_bad"

    // Control
    function enableWifi(enabled = true): void {
        const cmd = enabled ? "on" : "off";
        enableWifiProc.exec(["nmcli", "radio", "wifi", cmd]);
    }

    function toggleWifi(): void {
        enableWifi(!wifiEnabled);
    }

    function rescanWifi(): void {
        if (rescanProcess.running || connectProc.running) return;
        root.wifiScanError = "";
        root.scanRevision += 1;
        rescanProcess.running = true;
    }

    function connectToWifiNetwork(accessPoint: WifiAccessPoint): void {
        accessPoint.askingPassword = false;
        root.wifiConnectTarget = accessPoint;
        // We use this instead of `nmcli connection up SSID` because this also creates a connection profile
        connectProc.exec(["nmcli", "dev", "wifi", "connect", accessPoint.ssid])

    }

    function disconnectWifiNetwork(): void {
        if (active) disconnectProc.exec(["nmcli", "connection", "down", active.ssid]);
    }

    function openPublicWifiPortal() {
        Quickshell.execDetached(["xdg-open", "https://nmcheck.gnome.org/"]) // From some StackExchange thread, seems to work
    }

    function changePassword(network: WifiAccessPoint, password: string, username = ""): void {
        // TODO: enterprise wifi with username
        network.askingPassword = false;
        root.wifiConnectTarget = network;
        changePasswordProc.exec({
            "environment": {
                "PASSWORD": password,
                "SSID": network.ssid
            },
            "command": ["bash", "-c", 'nmcli connection modify "$SSID" wifi-sec.psk "$PASSWORD"']
        })
    }

    Process {
        id: enableWifiProc
        onExited: (exitCode, exitStatus) => {
            root.update();
            if (exitCode === 0) root.refreshNetworks();
        }
    }

    Process {
        id: connectProc
        environment: ({
            LANG: "C",
            LC_ALL: "C"
        })
        stdout: SplitParser {
            onRead: line => {
                // print(line)
                getNetworks.running = true
            }
        }
        stderr: SplitParser {
            onRead: line => {
                // print("err:", line)
                if (line.includes("Secrets were required")) {
                    if (root.wifiConnectTarget) root.wifiConnectTarget.askingPassword = true
                }
            }
        }
        onExited: (exitCode, exitStatus) => {
            if (root.wifiConnectTarget) root.wifiConnectTarget.askingPassword = (exitCode !== 0);
            root.wifiConnectTarget = null;
            root.update();
        }
    }

    Process {
        id: disconnectProc
        onExited: root.update()
        stdout: SplitParser {
            onRead: getNetworks.running = true
        }
    }

    Process {
        id: changePasswordProc
        onExited: (exitCode, exitStatus) => {
            if (!root.wifiConnectTarget) return;
            if (exitCode === 0) root.connectToWifiNetwork(root.wifiConnectTarget);
            else {
                root.wifiConnectTarget.askingPassword = true;
                root.wifiConnectTarget = null;
            }
        }
    }

    function applyNetworks(text) {
        const found = NmcliParser.networks(text);
        const previous = [...root.wifiNetworks];
        const next = found.map(network => {
            // Keep the object (and password field) stable across signal/BSSID changes.
            const existing = previous.find(n => n.ssid === network.ssid);
            if (existing) {
                existing.lastIpcObject = network;
                return existing;
            }
            return apComp.createObject(root, { lastIpcObject: network });
        });
        if (root.wifiConnectTarget && !next.includes(root.wifiConnectTarget))
            next.push(root.wifiConnectTarget);
        root.wifiNetworks = next;
        previous.filter(n => !next.includes(n)).forEach(n => n.destroy());
        root.networkStrength = root.active?.strength ?? 0;
    }

    function refreshNetworks() {
        if (!getNetworks.running && !rescanProcess.running) getNetworks.running = true;
    }

    Process {
        id: rescanProcess
        command: ["nmcli", "--wait", "12", "-g", "ACTIVE,SIGNAL,FREQ,SSID,BSSID,SECURITY",
            "device", "wifi", "list", "--rescan", "yes"]
        environment: ({ LANG: "C", LC_ALL: "C" })
        stdout: StdioCollector { id: scanOutput }
        stderr: StdioCollector { id: scanError }
        onExited: (exitCode, exitStatus) => {
            if (exitCode === 0) {
                root.applyNetworks(scanOutput.text);
                root.wifiLastScan = Qt.formatTime(new Date(), "hh:mm:ss");
                root.wifiScanError = "";
            } else {
                root.wifiScanError = scanError.text.trim() || "Wi-Fi scan failed. Try Refresh.";
            }
            root.update();
        }
    }

    // Monitor events refresh cached access points as well as connection status.
    // Debouncing coalesces bursts without spawning a process for every event.
    function update() { statusDebounce.restart(); }
    Timer {
        id: statusDebounce
        interval: 150
        onTriggered: {
            if (!updateConnectionType.running) updateConnectionType.startCheck();
            if (!wifiStatusProcess.running) wifiStatusProcess.running = true;
            if (!updateNetworkName.running) updateNetworkName.running = true;
            root.refreshNetworks();
        }
    }
    Timer {
        id: subscriberRetry
        interval: 3000
        onTriggered: subscriber.running = true
    }
    Process {
        id: subscriber
        running: true
        command: ["nmcli", "monitor"]
        environment: ({ LANG: "C", LC_ALL: "C" })
        stdout: SplitParser { onRead: root.update() }
        onExited: subscriberRetry.restart()
    }

    Process {
        id: updateConnectionType
        property string buffer
        command: ["sh", "-c", "nmcli -t -f TYPE,STATE d status && nmcli -t -f CONNECTIVITY g"]
        running: true
        function startCheck() {
            buffer = "";
            updateConnectionType.running = true;
        }
        stdout: SplitParser {
            onRead: data => {
                updateConnectionType.buffer += data + "\n";
            }
        }
        environment: ({ LANG: "C", LC_ALL: "C" })
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) return;
            const state = NmcliParser.connection(buffer);
            root.wifiStatus = state.status;
            root.ethernet = state.ethernet;
            root.wifi = state.wifi;
        }
    }

    Process {
        id: updateNetworkName
        command: ["sh", "-c", "nmcli -t -f NAME c show --active | head -1"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: root.networkName = text.trim()
        }
    }

    Process {
        id: wifiStatusProcess
        command: ["nmcli", "radio", "wifi"]
        Component.onCompleted: running = true
        environment: ({
            LANG: "C",
            LC_ALL: "C"
        })
        stdout: StdioCollector {
            onStreamFinished: {
                const wasEnabled = root.wifiEnabled;
                root.wifiEnabled = text.trim() === "enabled";
                if (!root.wifiEnabled) {
                    root.wifiStatus = "disabled";
                    root.applyNetworks("");
                } else if (!wasEnabled) root.rescanWifi();
            }
        }
    }

    Process {
        id: getNetworks
        property int requestRevision: 0
        onStarted: requestRevision = root.scanRevision
        running: true
        command: ["nmcli", "--wait", "8", "-g", "ACTIVE,SIGNAL,FREQ,SSID,BSSID,SECURITY",
            "device", "wifi", "list", "--rescan", "no"]
        environment: ({ LANG: "C", LC_ALL: "C" })
        stdout: StdioCollector { id: networksOutput }
        onExited: (exitCode, exitStatus) => {
            // Never overwrite a new scan with an older cached request.
            if (exitCode === 0 && !rescanProcess.running && requestRevision === root.scanRevision) root.applyNetworks(networksOutput.text);
        }
    }

    Component {
        id: apComp

        WifiAccessPoint {}
    }
}
