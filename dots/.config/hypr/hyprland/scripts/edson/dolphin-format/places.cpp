// SPDX-License-Identifier: GPL-3.0-or-later
#include <QApplication>
#include <QEvent>
#include <QGenericPlugin>
#include <QIcon>
#include <QMenu>
#include <QProcess>
#include <QStandardPaths>
#include <KFilePlacesModel>
#include <solid/block.h>

class PlacesActions final : public QObject {
    Q_OBJECT
public:
    PlacesActions() { qApp->installEventFilter(this); }
protected:
    bool eventFilter(QObject *obj, QEvent *event) override {
        if (event->type() == QEvent::Show && obj->inherits("KFilePlacesView")) {
            connect(obj, SIGNAL(contextMenuAboutToShow(QModelIndex,QMenu*)), this,
                    SLOT(addFormat(QModelIndex,QMenu*)), Qt::UniqueConnection);
        }
        return false;
    }
private slots:
    void addFormat(const QModelIndex &index, QMenu *menu) {
        const QString helper = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
            + "/quickshell/ii/scripts/removable/format_drive.py";
        if (!index.isValid()) {
            // Blank media may have no Places row until a filesystem exists.
            // Explicitly offer the external-volume chooser on the empty sidebar.
            QProcess probe;
            probe.start("/usr/bin/python3", {helper, "--list"});
            if (!probe.waitForFinished(1800)) { probe.kill(); probe.waitForFinished(250); return; }
            if (probe.exitCode()!=0 || probe.readAllStandardOutput().isEmpty()) return;
            auto *action=new QAction(QIcon::fromTheme("drive-removable-media"), tr("Format removable volume…"),menu);
            menu->insertAction(menu->actions().value(0),action);
            connect(action,&QAction::triggered,menu,[helper]() {
                QProcess::startDetached("/usr/bin/python3",{helper});
            });
            return;
        }
        const auto *model = qobject_cast<const KFilePlacesModel *>(index.model());
        if (!model || !model->isDevice(index)) return;
        const auto device = model->deviceForIndex(index);
        const auto *block = device.as<Solid::Block>();
        if (!block) return;
        const QString path = block->device();
        // Check eligibility at menu-open time; bind the exact disk incarnation
        // to the later click. No privilege or format operation in Dolphin.
        QProcess probe;
        probe.start("/usr/bin/python3", {helper, "--identify", path});
        if (!probe.waitForFinished(1800)) { probe.kill(); probe.waitForFinished(250); return; }
        if (probe.exitStatus()!=QProcess::NormalExit || probe.exitCode()!=0) return;
        const QString token = QString::fromLatin1(probe.readAllStandardOutput().trimmed());
        if (token.size()!=64) return;
        auto *action=new QAction(QIcon::fromTheme("drive-removable-media"), tr("Format…"), menu);
        action->setToolTip(tr("Open the format dialog for this removable volume"));
        menu->insertAction(menu->actions().value(0),action);
        connect(action,&QAction::triggered,menu,[path,helper,token]() {
            QProcess::startDetached("/usr/bin/python3",{helper,"--device",path,"--token",token});
        });
    }
};

class FormatPlugin final : public QGenericPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QGenericPluginFactoryInterface_iid FILE "keys.json")
public:
    QObject *create(const QString &key, const QString &) override {
        if (key.compare("ii-places-format",Qt::CaseInsensitive)==0) return new PlacesActions;
        return nullptr;
    }
};
#include "places.moc"
