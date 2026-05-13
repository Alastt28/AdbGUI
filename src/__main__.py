#!/usr/bin/python3
import os, sys, shutil, threading
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QObject, Slot, Property, Signal, QTimer
from adb_manager import AdbManager
from database_manager import DatabaseManager

class AdbBridge(QObject):
    appsChanged = Signal()
    loadingChanged = Signal()
    statusChanged = Signal()

    def __init__(self):
        super().__init__()
        self.adb = AdbManager()
        self.db = DatabaseManager()
        self.icon_cache = os.path.join(os.path.expanduser("~"), ".cache", "adbgui", "icons")
        os.makedirs(self.icon_cache, exist_ok=True)

        # Состояние
        self._cache = [] # Полный список данных
        self._model = [] # Отфильтрованный список для QML
        self._loading = False
        self._last_filter = "all"
        self._device_connected = False

        # Подписки на события
        self.db.dbUpdated.connect(self.refresh)
        self.db.dbUpdated.connect(lambda: print("[Main] Сигнал dbUpdated получен"))

        # Загрузка базы и запуск мониторинга устройства
        self.db.load_initial_data()
        self.db.sync_with_github()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_device)
        self.timer.start(3000)

    # --- Свойства для QML ---
    @Property(bool, notify=loadingChanged)
    def Loading(self): return self._loading

    @Property(list, notify=appsChanged)
    def apps_model(self): return self._model

    @Property(str, notify=statusChanged)
    def app_count_text(self): return f"Приложений: {len(self._model)}"

    # --- Публичные методы (Slot) ---
    @Slot()
    @Slot(str)
    def load_apps(self, filter_type="all"):
        if self._loading: return
        self._last_filter = filter_type
        if not self._cache:
            self._set_loading(True)
            threading.Thread(target=self._fetch_data_worker, daemon=True).start()
        else:
            self._apply_filter()

    @Slot()
    def refresh(self):
        self._cache = []
        self.load_apps(self._last_filter)

    @Slot(str)
    def freeze_app(self, pkg_id):
        if self.adb.freeze_app(pkg_id):
            self._update_app_status(pkg_id, True)

    @Slot(str)
    def unfreeze_app(self, pkg_id):
        if self.adb.unfreeze_app(pkg_id):
            self._update_app_status(pkg_id, False)

    @Slot(str, result=bool)
    def uninstall_app(self, pkg_id):
        if self.adb.uninstall_app(pkg_id):
            self._cache = [a for a in self._cache if a['id'] != pkg_id]
            self._apply_filter()
            return True
        return False

    # --- Внутренняя логика ---

    def _set_loading(self, v):
        self._loading = v
        self.loadingChanged.emit()

    def _update_app_status(self, pkg_id, is_off):
        for app in self._cache:
            if app['id'] == pkg_id:
                app['is_off'] = is_off
                break
        self._apply_filter()

    def _check_device(self):
        connected = self.adb.is_device_connected()
        if connected != self._device_connected:
            self._device_connected = connected
            self.statusChanged.emit()
            if connected:
                self.adb.ensure_bridge_installed()
                self.refresh()
            else:
                self._clear_icons_cache()
                self._loading = False
                self._cache, self._model = [], []
                self.loadingChanged.emit()
                self.appsChanged.emit()

    @Property(bool, notify=statusChanged)
    def deviceConnected(self):
        return self._device_connected

    def _fetch_data_worker(self):
        try:
            if not self._cache:
                raw = self.adb.get_processed_apps(self.adb.get_all_labels())
                self.adb.download_all_icons(self.icon_cache)
                for app in raw:
                    pkg = app['id']
                    info = self.db.get_info(pkg)
                    app.update({
                        'description': info.get('description', "Нет описания"),
                        'recommendation': info.get('removal', "unknown"),
                        'icon': f"file://{self.icon_cache}/{pkg}.png" if os.path.exists(f"{self.icon_cache}/{pkg}.png") else "package-x-generic"
                    })
                self._cache = raw

            self._apply_filter()
        finally:
            self._set_loading(False)

    def _apply_filter(self):
        f = self._last_filter
        self._model = [a for a in self._cache if
            f == "all" or
            (f == "system" and a['is_system']) or
            (f == "user" and a['is_user']) or
            (f == "frozen" and a['is_off'])
        ]
        self.appsChanged.emit()
        self.statusChanged.emit()

    def _clear_icons_cache(self):
        if os.path.exists(self.icon_cache):
            for filename in os.listdir(self.icon_cache):
                file_path = os.path.join(self.icon_cache, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"[Bridge/main.py] Не удалось удалить {file_path}: {e}")
            print(f"[Bridge/main.py] Кэш иконок очищен: {self.icon_cache}")

    def clear_cache(self):
        if os.path.exists(self.icon_cache):
            shutil.rmtree(self.icon_cache, ignore_errors=True)

def main():
    if not os.path.exists("/.flatpak-info"):
        os.environ.update({
            "QML2_IMPORT_PATH": "/usr/lib/qt6/qml",
            "QT_PLUGIN_PATH": "/usr/lib/qt6/plugins",
            "QT_QPA_PLATFORMTHEME": "kde",
            "QT_QUICK_CONTROLS_STYLE": "org.kde.desktop",
            "XDG_CURRENT_DESKTOP": "KDE"
        })

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AdbGUI")

    engine = QQmlApplicationEngine()
    bridge = AdbBridge()
    engine.rootContext().setContextProperty("backend", bridge)

    qml_file = Path(__file__).parent / "main.qml"
    if os.path.exists("/.flatpak-info"):
        qml_file = Path("/app/lib/python3.13/site-packages/main.qml")

    engine.load(QUrl.fromLocalFile(str(qml_file)))

    app.aboutToQuit.connect(bridge.clear_cache)
    sys.exit(app.exec() if engine.rootObjects() else -1)

if __name__ == "__main__":
    main()