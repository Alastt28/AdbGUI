import subprocess, os

class AdbManager:
    def __init__(self):
        self.expected_bridge_version = 3
        self.bridge_path = self._find_bridge_apk()

    def _find_bridge_apk(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base_dir, "data", "bin", "bridge.apk")
        if os.path.exists(candidate):
            return candidate

        paths = [
            os.path.join(os.path.dirname(__file__), "bridge.apk"),
            "/app/share/adbgui/bridge.apk",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return ""

    def get_installed_bridge_version(self):
        try:
            res = self.run_command(["shell", "dumpsys", "package", "com.adbgui.bridge"])
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    if "versionCode=" in line:
                        parts = line.strip().split()
                        for p in parts:
                            if p.startswith("versionCode="):
                                return int(p.split("=")[1])
        except Exception as e:
            print(f"Ошибка при проверке версии моста: {e}")
        return 0

    def get_devices_count(self):
        try:
            res = self.run_command(["devices"])
            lines = [l for l in res.stdout.strip().split('\n')[1:] if "\tdevice" in l]
            return len(lines)
        except:
            return 0

    def is_device_connected(self):
        try:
            result = self.run_command(["devices"])
            lines = result.stdout.strip().split('\n')
            return len(lines) > 1 and any("\tdevice" in line for line in lines[1:])
        except Exception:
            return False

    def run_command(self, args):
        try:
            cmd = ["adb"] + args
            return subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except Exception as e:
            class Error: returncode = 1; stderr = str(e); stdout = ""
            return Error()

    def ensure_bridge_installed(self):
        res = self.run_command(["shell", "pm", "list", "packages", "com.adbgui.bridge"])
        if "com.adbgui.bridge" not in res.stdout:
            print("[ADB] Мост не найден, установка...")
            self._install_bridge()
            return

        current_version = self.get_installed_bridge_version()
        print(f"[ADB] Версия моста на устройстве: {current_version}, ожидается: {self.expected_bridge_version}")

        if current_version < self.expected_bridge_version:
            print("[ADB] Версия моста устарела, обновление...")
            self._install_bridge()

    def _install_bridge(self):
        if self.bridge_path and os.path.exists(self.bridge_path):
            res = self.run_command(["install", "-r", "-g", self.bridge_path])
            if res.returncode == 0:
                print("[ADB] Мост успешно установлен/обновлен.")
            else:
                print(f"[ADB] Ошибка установки/обновления: {res.stderr}")
        else:
            print("[ADB] Критическая ошибка: APK моста не найден. Установка невозможна.")

    def get_all_labels(self):
        labels = {}
        res = self.run_command(["shell", "content", "query", "--uri", "content://com.adbgui.bridge/all"])

        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if "package=" in line and "label=" in line:
                    try:
                        pkg_start = line.find("package=") + len("package=")
                        lbl_start = line.find("label=") + len("label=")
                        pkg_part = line[pkg_start:].split(",")[0].strip()
                        lbl_part = line[lbl_start:].split(",")[0].strip().strip("'\"")

                        if lbl_part and lbl_part.lower() != "null":
                            labels[pkg_part] = lbl_part

                    except Exception as e:
                        print(f"[ADB] Ошибка парсинга строки: {e}")
                        continue
        return labels

    def download_all_icons(self, icons_cache_path):
        print("[ADB] Выгрузка иконок...")
        self.run_command(["shell", "content", "query", "--uri", "content://com.adbgui.bridge/export_icons"])
        remote_path = "/sdcard/Android/data/com.adbgui.bridge/cache/icons/."
        print(f"[ADB] Синхронизация: {remote_path} -> {icons_cache_path}")

        try:
            result = subprocess.run(
                ["adb", "pull", remote_path, icons_cache_path],
                capture_output=True,
                text=True,
                timeout=20
            )

            if result.returncode == 0:
                print(f"[ADB] Иконки успешно синхронизированы в {icons_cache_path}")
                return True
            else:
                print(f"[ADB] Ошибка синхронизации иконок: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("[ADB] Ошибка: Превышено время ожидания adb pull")
            return False
        except Exception as e:
            print(f"[ADB] Ошибка при выгрузке: {e}")
            return False

    def get_processed_apps(self, labels_cache):
        all_pkgs_raw = self.run_command(["shell", "pm", "list", "packages", "-f", "-u"]).stdout.splitlines()
        system_pkgs = {l.split(":")[-1].strip() for l in self.run_command(["shell", "pm", "list", "packages", "-s", "-u"]).stdout.splitlines()}
        installed_pkgs = {l.split(":")[-1].strip() for l in self.run_command(["shell", "pm", "list", "packages"]).stdout.splitlines()}
        disabled_pkgs = {l.split(":")[-1].strip() for l in self.run_command(["shell", "pm", "list", "packages", "-d"]).stdout.splitlines()}

        apps_data = []
        for line in all_pkgs_raw:
            if "=" not in line: continue
            pkg_id = line.rsplit("=", 1)[1].strip()

            if pkg_id in ["io.github.Alastt28.AdbGUI", "com.adbgui.bridge"]: continue

            is_system = pkg_id in system_pkgs
            is_user = not is_system
            is_off = (pkg_id in disabled_pkgs) or (pkg_id not in installed_pkgs)

            apps_data.append({
                'id': pkg_id,
                'title': labels_cache.get(pkg_id, pkg_id),
                'is_off': is_off,
                'is_user': is_user,
                'is_system': is_system
            })

        apps_data.sort(key=lambda x: (x['is_system'], x['title'].lower()))
        return apps_data

    def freeze_app(self, pkg_id):
        res = self.run_command(["shell", "pm", "uninstall", "-k", "--user", "0", pkg_id])
        return res.returncode == 0

    def unfreeze_app(self, pkg_id):
        res = self.run_command(["shell", "cmd", "package", "install-existing", pkg_id])

        # Если приложение было отключено обычным способом (pm disable)
        self.run_command(["shell", "pm", "enable", pkg_id])
        return res.returncode == 0

    def uninstall_app(self, pkg_id):
        res = self.run_command(["shell", "pm", "uninstall", pkg_id])
        return res.returncode == 0
