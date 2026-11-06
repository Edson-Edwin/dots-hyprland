import QtQuick
import qs.modules.common

Canvas {
    id: root
    property var values: []
    property var secondaryValues: []
    property color lineColor: Appearance.colors.colPrimary
    property color secondaryColor: Appearance.colors.colTertiary
    property color gridColor: Appearance.colors.colOutlineVariant
    property real ceiling: 100
    onValuesChanged: requestPaint()
    onSecondaryValuesChanged: requestPaint()
    onLineColorChanged: requestPaint()
    onSecondaryColorChanged: requestPaint()
    onGridColorChanged: requestPaint()
    onCeilingChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if (visible) requestPaint()
    onPaint: {
        const ctx = getContext("2d"); ctx.reset();
        const w = width, h = height - 3, limit = Math.max(1, ceiling);
        ctx.strokeStyle = Qt.alpha(gridColor, .35); ctx.lineWidth = 1;
        for (let i = 1; i <= 3; ++i) {
            ctx.beginPath(); ctx.moveTo(0, h*i/3); ctx.lineTo(w, h*i/3); ctx.stroke();
        }
        function plot(data, color, fill) {
            if (data.length < 2) return;
            const step = w/59, start = w - (data.length-1)*step;
            function y(v) { return h - Math.min(1, Math.max(0, v/limit))*(h-4); }
            ctx.beginPath(); ctx.moveTo(start, y(data[0]));
            for (let i=1; i<data.length; ++i) ctx.lineTo(start+i*step, y(data[i]));
            ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
            if (fill) {
                ctx.lineTo(w,h);ctx.lineTo(start,h);ctx.closePath();
                const gradient=ctx.createLinearGradient(0,0,0,h);
                gradient.addColorStop(0,Qt.alpha(color,.3));gradient.addColorStop(1,Qt.alpha(color,.02));
                ctx.fillStyle=gradient;ctx.fill();
            }
            ctx.beginPath();ctx.arc(w-2,y(data[data.length-1]),2,0,2*Math.PI);ctx.fillStyle=color;ctx.fill();
        }
        plot(values,lineColor,true);plot(secondaryValues,secondaryColor,false);
    }
}
