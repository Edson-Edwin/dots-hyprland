import qs
import qs.modules.common
import qs.modules.common.widgets
import QtQuick.Controls
import qs.services
import QtQuick
import QtQuick.Layouts

MouseArea {
    id: root
    property bool borderless: Config.options.bar.borderless
    property bool alwaysShowAllResources: false
    implicitWidth: rowLayout.implicitWidth + rowLayout.anchors.leftMargin + rowLayout.anchors.rightMargin
    implicitHeight: Appearance.sizes.barHeight
    hoverEnabled: !Config.options.bar.tooltips.clickToShow

    RowLayout {
        id: rowLayout

        spacing: 0
        anchors.fill: parent
        anchors.leftMargin: 4
        anchors.rightMargin: 4

        MouseArea {
            visible: ResourceUsage.pressureResource !== ""
            implicitWidth: 24
            implicitHeight: root.implicitHeight
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            readonly property string description: ({"cpu":"CPU","memory":"Memory","io":"Disk I/O"}[ResourceUsage.pressureResource] ?? "")+" pressure · "+Math.round(ResourceUsage.pressurePercent)+"%"
            Accessible.role: Accessible.Button
            Accessible.name: description
            Accessible.onPressAction: GlobalStates.pressureMonitorRequested(ResourceUsage.pressureResource)
            ToolTip.visible: containsMouse
            ToolTip.text: description
            MaterialSymbol {
                anchors.centerIn: parent
                text: "monitor_heart"
                iconSize: Appearance.font.pixelSize.normal
                color: Appearance.barForeground(Appearance.colors.colError)
            }
            onClicked: GlobalStates.pressureMonitorRequested(ResourceUsage.pressureResource)
        }

        Resource {
            iconName: "memory"
            percentage: ResourceUsage.memoryUsedPercentage
            warningThreshold: Config.options.bar.resources.memoryWarningThreshold
        }

        Resource {
            iconName: "swap_horiz"
            percentage: ResourceUsage.swapUsedPercentage
            shown: (Config.options.bar.resources.alwaysShowSwap && percentage > 0) || 
                (MprisController.activePlayer?.trackTitle == null) ||
                root.alwaysShowAllResources
            Layout.leftMargin: shown ? 6 : 0
            warningThreshold: Config.options.bar.resources.swapWarningThreshold
        }

        Resource {
            iconName: "planner_review"
            percentage: ResourceUsage.cpuUsage
            shown: Config.options.bar.resources.alwaysShowCpu || 
                !(MprisController.activePlayer?.trackTitle?.length > 0) ||
                root.alwaysShowAllResources
            Layout.leftMargin: shown ? 6 : 0
            warningThreshold: Config.options.bar.resources.cpuWarningThreshold
        }

    }

    ResourcesPopup {
        hoverTarget: root
    }
}
