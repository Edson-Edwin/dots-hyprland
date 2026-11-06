.pragma library

// nmcli escapes both ':' and '\\' in terse fields, including SSIDs.
function fields(line) {
    var result = [], current = "", escaped = false;
    for (var i = 0; i < line.length; ++i) {
        var c = line[i];
        if (escaped) { current += c; escaped = false; }
        else if (c === "\\") escaped = true;
        else if (c === ":") { result.push(current); current = ""; }
        else current += c;
    }
    if (escaped) current += "\\";
    result.push(current);
    return result;
}

function networks(text) {
    var grouped = new Map();
    text.split("\n").filter(line => line.length > 0).forEach(line => {
        var f = fields(line);
        if (f.length < 6 || !f[3]) return;
        var net = { active: f[0] === "yes", strength: Number(f[1]) || 0,
            frequency: Number(f[2]) || 0, ssid: f[3], bssid: f[4],
            security: f[5] === "--" ? "" : f[5] };
        var previous = grouped.get(net.ssid);
        if (!previous || (net.active && !previous.active)
            || (net.active === previous.active && net.strength > previous.strength))
            grouped.set(net.ssid, net);
    });
    return Array.from(grouped.values());
}

function connection(text) {
    var lines = text.trim().split("\n");
    var connectivity = lines.pop();
    var result = { wifi: false, ethernet: false, status: "disconnected" };
    lines.forEach(line => {
        var f = fields(line);
        var connected = f[1] === "connected" || (f[1] || "").startsWith("connected (");
        if (f[0] === "ethernet" && connected) result.ethernet = true;
        if (f[0] !== "wifi") return;
        if (connected) {
            result.wifi = connectivity !== "limited";
            result.status = connectivity === "limited" ? "limited" : "connected";
        } else if ((f[1] || "").startsWith("connecting")) result.status = "connecting";
        else if (f[1] === "unavailable") result.status = "disabled";
    });
    return result;
}
