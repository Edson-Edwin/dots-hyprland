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
#include <QDBusConnection>
#include <QDockWidget>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMainWindow>
#include <QPointer>
#include <QPushButton>
#include <QTimer>
#include <QVBoxLayout>

static QString helperPath() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
        + "/quickshell/ii/scripts/removable/format_drive.py";
}

// KFilePlacesModel only lists volumes it can mount. Keep these rows separate
// from its bookmarks so unplugging a disk leaves no persistent Places entry.
class UnrecognizedDrives final : public QObject {
    Q_OBJECT
public:
    UnrecognizedDrives(QMainWindow *window, QDockWidget *places)
        : QObject(window), window(window), places(places) {
        debounce.setSingleShot(true);
        debounce.setInterval(350);
        connect(&debounce, &QTimer::timeout, this, [this] {
            if (probe.state() != QProcess::NotRunning) {
                rescan = true;
                return;
            }
            probe.start("/usr/bin/python3", {helperPath(), "--unrecognized"});
        });
        connect(&probe, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
            const auto data = QJsonDocument::fromJson(probe.readAllStandardOutput());
            if (status == QProcess::NormalExit && code == 0 && data.isArray())
                updateRows(data.array());
            if (rescan) {
                rescan = false;
                debounce.start();
            }
        });
        auto bus = QDBusConnection::systemBus();
        const QString service = "org.freedesktop.UDisks2";
        for (const QString &signal : {QString("InterfacesAdded"), QString("InterfacesRemoved")})
            bus.connect(service, "/org/freedesktop/UDisks2", "org.freedesktop.DBus.ObjectManager",
                        signal, this, SLOT(refresh()));
        bus.connect(service, {}, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                    this, SLOT(refresh()));
        refresh();
    }
private slots:
    void refresh() { debounce.start(); }
private:
    void updateRows(const QJsonArray &volumes) {
        if (!places || (initialized && volumes == previous)) return;
        previous = volumes;
        initialized = true;
        if (volumes.isEmpty()) {
            if (panel) panel->hide();
            return;
        }
        if (!panel) {
            panel = new QDockWidget(tr("Unrecognized drives"), window);
            panel->setObjectName("ii-unrecognized-drives");
            panel->setFeatures(QDockWidget::NoDockWidgetFeatures);
            const auto area = window->dockWidgetArea(places);
            window->addDockWidget(area == Qt::NoDockWidgetArea ? Qt::LeftDockWidgetArea : area, panel);
            if (!places->isFloating()) window->splitDockWidget(places, panel, Qt::Vertical);
        }
        auto *content = new QWidget(panel);
        auto *layout = new QVBoxLayout(content);
        for (auto value : volumes) {
            const auto volume = value.toObject();
            auto *button = new QPushButton(QIcon::fromTheme("drive-removable-media"),
                                           volume["title"].toString(), content);
            const bool emptyTable = volume["emptyTable"].toBool();
            if (emptyTable) {
                button->setText(volume["title"].toString() + "\n" + tr("No partitions"));
                button->setToolTip(tr("Open Disks to inspect the free space on this drive."));
            } else {
                button->setToolTip(tr("No recognized filesystem. Click to inspect this volume in Disks."));
            }
            const QStringList args{helperPath(), "--device", volume["path"].toString(),
                                   "--token", volume["token"].toString()};
            connect(button, &QPushButton::clicked, button, [args] {
                QProcess::startDetached("/usr/bin/python3", args + QStringList{"--inspect"});
            });
            if (!emptyTable) {
                button->setContextMenuPolicy(Qt::ActionsContextMenu);
                auto *format = button->addAction(tr("Format…"));
                connect(format, &QAction::triggered, button, [args] {
                    QProcess::startDetached("/usr/bin/python3", args);
                });
            }
            layout->addWidget(button);
        }
        auto *old = panel->widget();
        panel->setWidget(content);
        if (old) old->deleteLater();
        panel->show();
        window->resizeDocks({panel}, {panel->sizeHint().height()}, Qt::Vertical);
    }

    QMainWindow *window;
    QPointer<QDockWidget> places;
    QPointer<QDockWidget> panel;
    QProcess probe;
    QTimer debounce;
    QJsonArray previous;
    bool initialized = false;
    bool rescan = false;
};

class PlacesActions final : public QObject {
    Q_OBJECT
public:
    PlacesActions() { qApp->installEventFilter(this); }
protected:
    bool eventFilter(QObject *obj, QEvent *event) override {
        if (event->type() == QEvent::Show && obj->inherits("KFilePlacesView")) {
            auto *view = qobject_cast<QWidget *>(obj);
            auto *window = qobject_cast<QMainWindow *>(view->window());
            auto *parent = view->parentWidget();
            while (parent && !qobject_cast<QDockWidget *>(parent))
                parent = parent->parentWidget();
            if (window && parent && !window->findChild<UnrecognizedDrives *>())
                new UnrecognizedDrives(window, qobject_cast<QDockWidget *>(parent));
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
