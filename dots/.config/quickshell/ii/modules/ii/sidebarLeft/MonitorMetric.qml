import QtQuick
import QtQuick.Layouts
import qs.modules.common
import qs.modules.common.widgets

Rectangle {
    id: root
    property string title
    property string value
    property string detail
    property var history: []
    property color accent: Appearance.colors.colPrimary
    implicitHeight: 150
    radius: 18
    color: Appearance.colors.colLayer2
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 5
        StyledText { text: root.title; font.pixelSize: 12; color: Appearance.colors.colSubtext }
        StyledText { text: root.value; font.pixelSize: 28; font.weight: Font.DemiBold; color: root.accent }
        StyledText { text: root.detail; font.pixelSize: 11; color: Appearance.colors.colSubtext; Layout.fillWidth: true; elide: Text.ElideRight }
        MonitorChart { Layout.fillWidth: true; Layout.fillHeight: true; values: root.history; lineColor: root.accent }
    }
}
