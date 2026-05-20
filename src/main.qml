import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root
    Kirigami.Theme.colorSet: Kirigami.Theme.Window
    width: 900
    height: 700
    title: "AdbGUI"

    readonly property var adbBackend: backend
    property var selectedApps: []
    property var selectedAppsData: []
    property string selectionType: ""
    property bool selectionIsOff: false
    property bool selectionMode: selectedApps.length > 0
    readonly property bool selectionHasActive:
        selectedAppsData.some(a => !a.is_off)
    readonly property bool selectionHasFrozen:
        selectedAppsData.some(a => a.is_off)

    // Оверлей: устройство не подключено
    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
        z: 9999
        visible: root.adbBackend ? !root.adbBackend.deviceConnected : false

        MouseArea { anchors.fill: parent; enabled: visible }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 8
            icon.name: "device-notifier"
            text: "Устройство не обнаружено"
            explanation: "Подключите Android устройство с включенной отладкой по USB"
        }
    }

    // Оверлей: устройство подключено, но данные загружаются
    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
        z: 9999
        visible: root.adbBackend ? (root.adbBackend.deviceConnected && root.adbBackend.Loading) : false

        MouseArea { anchors.fill: parent; enabled: visible }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 8
            text: "Загрузка списка приложений..."
            ColumnLayout {
                Layout.alignment: Qt.AlignHCenter
                Controls.BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: visible
                }
            }
        }
    }

    // --- 2. ДИАЛОГИ ---
    Kirigami.PromptDialog {
        id: uninstallDialog
        property string currentPkgId: ""
        property string currentAppTitle: ""
        title: "Удаление приложения"
        subtitle: "Вы уверены, что хотите полностью удалить " + (currentAppTitle ? currentAppTitle : currentPkgId) + "? Все данные приложения будут стёрты."
        standardButtons: Controls.Dialog.Ok | Controls.Dialog.Cancel
        onAccepted: {
            if (backend) {
                let success = backend.uninstall_app(currentPkgId)
                let displayName = currentAppTitle ? currentAppTitle : currentPkgId
                if (success) {
                    root.showPassiveNotification("Приложение " + displayName + " удалено", "short")
                } else {
                    root.showPassiveNotification("Ошибка при удалении " + displayName, "long")
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: appInfoSheet
        property var appData: null
        contentItem: Controls.Pane {
            implicitWidth: Kirigami.Units.gridUnit * 25
            ColumnLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading {
                    text: appInfoSheet.appData ? appInfoSheet.appData.title : ""
                    level: 2
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
                Controls.Label {
                    text: appInfoSheet.appData ? appInfoSheet.appData.id : ""
                    opacity: 0.6
                    font.pointSize: 9
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                }
                Controls.Label {
                    text: (appInfoSheet.appData && appInfoSheet.appData.description) ? appInfoSheet.appData.description : "Нет описания"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    font.pointSize: 10
                }
            }
        }
    }

    // --- 3. ОСНОВНОЙ КОНТЕНТ ---
    pageStack.initialPage: Kirigami.ScrollablePage {
        id: mainPage

        titleDelegate: RowLayout {
            width: mainPage.width
            spacing: Kirigami.Units.smallSpacing
            Kirigami.Heading {
                text: backend ? backend.app_count_text : "Загрузка..."
                level: 1
                Layout.fillWidth: true
            }
            Kirigami.SearchField {
                id: searchField
                Layout.preferredWidth: Kirigami.Units.gridUnit * 15
                onTextChanged: listView.modelFilter = text
            }
            Controls.Button {
                icon.name: "view-refresh"
                enabled: !!(backend && !backend.Loading)
                flat: true
                onClicked: backend.refresh()
            }
        }

        header: Controls.TabBar {
            id: bar
            Layout.fillWidth: true
            Controls.TabButton { text: "Все"; onClicked: if (backend) backend.load_apps("all") }
            Controls.TabButton { text: "Системные"; onClicked: if (backend) backend.load_apps("system") }
            Controls.TabButton { text: "Пользовательские"; onClicked: if (backend) backend.load_apps("user") }
            Controls.TabButton { text: "Замороженные"; onClicked: if (backend) backend.load_apps("frozen") }
        }

        ListView {
            id: listView
            property string modelFilter: ""
            anchors.fill: parent
            model: root.adbBackend ? root.adbBackend.apps_model : []
            clip: true

            delegate: Controls.ItemDelegate {
                id: appDelegate
                readonly property bool isSelectable: !root.selectionMode ||
                    (modelData.is_system && root.selectionType === "system" && modelData.is_off === root.selectionIsOff) ||
                    (modelData.is_user && root.selectionType === "user")

                opacity: appDelegate.isSelectable ? 1.0 : 0.35
                width: listView.width
                visible: {
                    if (listView.modelFilter === "") return true;
                    return modelData.title.toLowerCase().includes(listView.modelFilter.toLowerCase()) ||
                           modelData.id.toLowerCase().includes(listView.modelFilter.toLowerCase())
                }
                height: visible ? implicitHeight : 0
                onClicked: {
                    if (!appDelegate.isSelectable) return
                    appInfoSheet.appData = modelData
                    appInfoSheet.open()
                }

                contentItem: RowLayout {
                    Controls.CheckBox {
                        visible: appDelegate.isSelectable
                        checked: root.selectedApps.includes(modelData.id)
                        onClicked: {
                            if (checked) {
                                root.selectionType = modelData.is_system ? "system" : "user"
                                root.selectionIsOff = modelData.is_off
                                root.selectedApps = [...root.selectedApps, modelData.id]
                                root.selectedAppsData = [...root.selectedAppsData, modelData]
                            } else {
                                root.selectedApps = root.selectedApps.filter(p => p !== modelData.id)
                                root.selectedAppsData = root.selectedAppsData.filter(a => a.id !== modelData.id)
                                if (root.selectedApps.length === 0) {
                                    root.selectionType = ""
                                    root.selectionIsOff = false
                                }
                            }
                        }
                    }
                    spacing: 12
                    Kirigami.Icon {
                        source: modelData.icon || "package-x-generic"
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 2
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 2
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Controls.Label { text: modelData.title; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                        Controls.Label { text: modelData.id; opacity: 0.6; font.pointSize: 9; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                    Controls.Label {
                        text: modelData.recommendation ? modelData.recommendation.toUpperCase() : ""
                        font.bold: true
                        font.pointSize: 8
                        color: {
                            let rec = modelData.recommendation ? modelData.recommendation.toLowerCase() : ""
                            if (rec === "recommended") return Kirigami.Theme.positiveTextColor
                            if (rec === "advanced") return "#f39c12"
                            if (rec === "expert" || rec === "unsafe") return Kirigami.Theme.negativeTextColor
                            return Kirigami.Theme.disabledTextColor
                        }
                    }
                    RowLayout {
                        Controls.Button {
                            icon.name: modelData.is_off ? "media-playback-start" : "system-shutdown"
                            flat: true
                            visible: modelData.is_system  && !root.selectionMode
                            onClicked: modelData.is_off ? backend.unfreeze_app(modelData.id) : backend.freeze_app(modelData.id)
                        }
                        Controls.Button {
                            icon.name: "edit-delete"
                            flat: true
                            visible: modelData.is_user  && !root.selectionMode
                            onClicked: {
                                uninstallDialog.currentPkgId = modelData.id
                                uninstallDialog.currentAppTitle = modelData.title
                                uninstallDialog.open()
                            }
                        }
                    }
                }
            }
        }
        footer: Controls.ToolBar {
            visible: root.selectionMode
            height: root.selectionMode ? implicitHeight : 0
            RowLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing

                Controls.Button {
                    text: "Снять выделение"
                    icon.name: "edit-clear"
                    flat: true
                    onClicked: {
                        root.selectedApps = []
                        root.selectedAppsData = []
                        root.selectionType = ""
                        root.selectionIsOff = false
                    }
                }
                Controls.Label {
                    text: "Выбрано: " + root.selectedApps.length
                    Layout.fillWidth: true
                    font.bold: true
                }
                Controls.Button {
                    text: "Заморозить"
                    icon.name: "system-shutdown"
                    visible: root.selectionType === "system" && root.selectionHasActive
                    onClicked: {
                        backend.freeze_apps(root.selectedApps)
                        root.selectedApps = []
                        root.selectedAppsData = []
                        root.selectionType = ""
                        root.selectionIsOff = false
                    }
                }
                Controls.Button {
                    text: "Разморозить"
                    icon.name: "media-playback-start"
                    visible: root.selectionType === "system" && root.selectionHasFrozen
                    onClicked: {
                        backend.unfreeze_apps(root.selectedApps)
                        root.selectedApps = []
                        root.selectedAppsData = []
                        root.selectionType = ""
                        root.selectionIsOff = false
                    }
                }
                Controls.Button {
                    text: "Удалить"
                    icon.name: "edit-delete"
                    visible: root.selectionType === "user"
                    onClicked: {
                        backend.uninstall_apps(root.selectedApps)
                        root.selectedApps = []
                        root.selectedAppsData = []
                        root.selectionType = ""
                        root.selectionIsOff = false
                    }
                }
            }
        }
    }
}