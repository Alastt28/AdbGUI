# window.py
#
# Copyright 2026 Alast
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess, threading, os
from gi.repository import Gtk, Gdk, Adw, GLib

@Gtk.Template(resource_path='/org/adb/gui/app_row.ui')
class AppRow(Adw.ActionRow):
    __gtype_name__ = 'AppRow'
    action_button = Gtk.Template.Child()
    select_checkbox = Gtk.Template.Child()

    def __init__(self, app_name, package_name, is_off=False, is_system=False):
        super().__init__()
        self.set_title(app_name)
        self.sort_label = str.casefold(app_name)
        self.package_name = package_name
        self.set_subtitle(package_name)
        self.package_name = package_name
        self.is_off = is_off
        self.is_system = is_system
        self.update_button_style()

    def update_button_style(self):
        for cls in ["delete-button", "freeze-button", "success-button"]:
            self.action_button.remove_css_class(cls)

        if self.is_system:
            if self.is_off:
                self.action_button.set_icon_name("view-refresh-symbolic")
                self.action_button.add_css_class("success-button")
            else:
                self.action_button.set_icon_name("system-shutdown-symbolic")
                self.action_button.add_css_class("freeze-button")
        else:
            self.action_button.set_icon_name("user-trash-symbolic")
            self.action_button.add_css_class("delete-button")

    def refresh_ui(self):
        root = self.get_root()
        if root:
            root.load_adb_apps()

    @Gtk.Template.Callback()
    def on_checkbox_toggled(self, checkbox):
        if getattr(self, '_internal_update', False):
            return

        window = self.get_root()
        if window and hasattr(window, "selected_rows"):
            if checkbox.get_active():
                window.selected_rows.add(self.package_name)
            else:
                window.selected_rows.discard(self.package_name)

            window.update_action_bar_visibility()

    @Gtk.Template.Callback()
    def on_action_clicked(self, button):
        if not self.is_system:
            self.on_delete_clicked(button)
        else:
            self.on_off_clicked(button)

    def on_off_clicked(self, button):
        action = "enable" if self.is_off else "disable-user"
        window = self.get_root()

        def work():
            try:
                subprocess.run(["adb", "shell", "pm", action, "--user", "0", self.package_name], check=True)

                def update_ui():
                    self.is_off = not self.is_off

                    if window and hasattr(window, 'add_row_to_correct_list'):
                        window.action_revealer.set_reveal_child(False)

                        parent_list = self.get_parent()
                        if parent_list:
                            parent_list.remove(self)

                        window.add_row_to_correct_list(
                            self.get_title(),
                            self.package_name,
                            self.is_off,
                            self.is_system,
                            not self.is_system
                        )

                        window.clear_selection()

                GLib.idle_add(update_ui)
            except Exception as e:
                print(f"Ошибка ADB: {e}")

        threading.Thread(target=work, daemon=True).start()

    def on_delete_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Удалить приложение?",
            body=f"Вы действительно хотите полностью удалить {self.get_title()}?",
        )
        dialog.add_response("cancel", "Отмена")
        dialog.add_response("delete", "Удалить")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog, response):
            if response == "delete":
                self.execute_uninstall()

        dialog.connect("response", on_response)
        dialog.present()

    def execute_uninstall(self):
        def work():
            try:
                subprocess.run(["adb", "shell", "pm", "uninstall", "--user", "0", self.package_name], check=True)
                GLib.idle_add(self.refresh_ui)
            except Exception as e:
                print(f"Ошибка при удалении {self.package_name}: {e}")

        threading.Thread(target=work, daemon=True).start()

@Gtk.Template(resource_path='/org/adb/gui/window.ui')
class AdbGuiWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AdbGuiWindow'

    status_spinner = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    page_apps_system = Gtk.Template.Child()
    page_apps_user = Gtk.Template.Child()
    page_apps_off = Gtk.Template.Child()
    apps_list = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    status_stack = Gtk.Template.Child()
    action_revealer = Gtk.Template.Child()
    bulk_disable_btn = Gtk.Template.Child()
    bulk_enable_btn = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_fetching = False
        self.labels_cache = {}
        self.selected_rows = set()
        self.needs_full_reload = False
        self.last_apps_count = 0
        self.search_bar.set_key_capture_widget(self)
        self.search_bar.connect_entry(self.search_entry)
        self.last_adb_output = ""
        self.load_adb_apps()
        self.apps_list.set_filter_func(self.filter_func)
        self.page_apps_system.set_filter_func(self.filter_func)
        self.page_apps_off.set_filter_func(self.filter_func)
        self.page_apps_user.set_filter_func(self.filter_func)
        self.main_stack.connect("notify::visible-child-name", self.on_tab_changed)
        GLib.timeout_add_seconds(3, self.auto_refresh)
        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            lst.set_filter_func(self.filter_func)
            lst.set_sort_func(self.sort_func)

        style_provider = Gtk.CssProvider()
        css_data = """
            .delete-button image { color: #e01b24; }
            .freeze-button image { color: #3584e4; }
            .success-button image { color: #2ec27e; }

            .delete-button:hover { background-color: rgba(224, 27, 36, 0.1); }
            .freeze-button:hover { background-color: rgba(53, 132, 228, 0.1); }
            .success-button:hover { background-color: rgba(46, 194, 126, 0.1); }
        """
        style_provider.load_from_data(css_data.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def clear_selection(self):
        self.action_revealer.set_reveal_child(False)

        self.selected_rows.clear()

        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            row = lst.get_first_child()
            while row:
                if hasattr(row, 'select_checkbox'):
                    row._internal_update = True
                    row.select_checkbox.set_active(False)
                    row._internal_update = False
                row = row.get_next_sibling()

    def sort_func(self, row1, row2):
        if row1.sort_label > row2.sort_label:
            return 1
        elif row1.sort_label < row2.sort_label:
            return -1
        return 0

    def _refresh_list_state(self, listbox):
        listbox.invalidate_filter()
        listbox.invalidate_sort()

    def on_tab_changed(self, stack, pspec):
        self.update_action_bar_visibility()

    def update_action_bar_visibility(self, *args):
        selected_count = len(self.selected_rows)
        selected_rows = []
        current_tab = self.main_stack.get_visible_child_name()
        target_list = self.get_active_list(current_tab)

        row = target_list.get_first_child()
        while row:
            if hasattr(row, 'select_checkbox') and row.select_checkbox.get_active():
                selected_rows.append(row)
            row = row.get_next_sibling()

        selected_count = len(selected_rows)

        all_rows = target_list.get_first_child()
        if selected_count > 0:
            first_selected_is_system = selected_rows[0].is_system
            while all_rows:
                if hasattr(all_rows, 'select_checkbox'):
                    is_different_type = all_rows.is_system != first_selected_is_system
                    if not all_rows.select_checkbox.get_active():
                        all_rows.set_sensitive(not is_different_type)
                all_rows = all_rows.get_next_sibling()
        else:
            while all_rows:
                all_rows.set_sensitive(True)
                all_rows = all_rows.get_next_sibling()

        if selected_count > 0:
            is_system = selected_rows[0].is_system

            if is_system:
                self.bulk_disable_btn.set_label(f"Заморозить ({selected_count})")
                self.bulk_disable_btn.remove_css_class("destructive-action")
            else:
                self.bulk_disable_btn.set_label(f"Удалить ({selected_count})")
                self.bulk_disable_btn.add_css_class("destructive-action")

            self.bulk_enable_btn.set_label(f"Разморозить ({selected_count})")

            if current_tab == "page_apps_off_id":
                self.bulk_disable_btn.set_visible(False)
                self.bulk_enable_btn.set_visible(True)
            else:
                self.bulk_disable_btn.set_visible(True)
                self.bulk_enable_btn.set_visible(False)

        self.action_revealer.set_reveal_child(selected_count > 0)

    def get_active_list(self, tab_name):
        mapping = {
            "page_apps_all_id": self.apps_list,
            "page_apps_system_id": self.page_apps_system,
            "page_apps_off_id": self.page_apps_off,
            "page_apps_user_id": self.page_apps_user
        }
        return mapping.get(tab_name, self.apps_list)

    @Gtk.Template.Callback()
    def on_bulk_disable_clicked(self, button):
        current_tab = self.main_stack.get_visible_child_name()
        target_list = self.get_active_list(current_tab)

        selected_rows = []
        row = target_list.get_first_child()
        while row:
            if hasattr(row, 'select_checkbox') and row.select_checkbox.get_active():
                selected_rows.append(row)
            row = row.get_next_sibling()

        if not selected_rows:
            return

        has_system = any(r.is_system for r in selected_rows)

        if not has_system:
            self.run_bulk_action("uninstall")
        else:
            self.run_bulk_action("disable-user")

    @Gtk.Template.Callback()
    def on_bulk_enable_clicked(self, button):
        self.run_bulk_action("enable")

    def run_bulk_action(self, action):
        current_tab = self.main_stack.get_visible_child_name()
        target_list = self.get_active_list(current_tab)

        packages_to_process = []
        row = target_list.get_first_child()

        while row:
            if hasattr(row, 'select_checkbox') and row.select_checkbox.get_active():
                packages_to_process.append(row.package_name)
            row = row.get_next_sibling()

        if not packages_to_process:
            return

        self.clear_selection()
        self.is_fetching = True

        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            lst.set_sort_func(None)

        def work():
            try:
                if action == "uninstall":
                    for pkg in packages_to_process:
                        subprocess.run(["adb", "shell", "pm", "uninstall", "--user", "0", pkg], capture_output=True)
                else:
                    commands = "; ".join([f"pm {action} --user 0 {pkg}" for pkg in packages_to_process])
                    full_cmd = ["adb", "shell", commands]
                    subprocess.run(full_cmd, capture_output=True, timeout=15)
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                self.is_fetching = False
                self.needs_full_reload = True
                GLib.idle_add(self.load_adb_apps)

        threading.Thread(target=work, daemon=True).start()

    def finish_bulk_action(self):
        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            lst.set_sort_func(self.sort_func)
        self.load_adb_apps()

    @Gtk.Template.Callback()
    def on_clear_selection_clicked(self, button):
        self.clear_selection()

    def trigger_refresh(self):
        self.load_adb_apps()

    def filter_func(self, row):
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True

        title = row.get_title().lower()
        subtitle = row.get_subtitle().lower()

        return search_text in title or search_text in subtitle

    @Gtk.Template.Callback()
    def on_search_changed(self, entry):
        self.apps_list.invalidate_filter()
        self.page_apps_system.invalidate_filter()
        self.page_apps_off.invalidate_filter()
        self.page_apps_user.invalidate_filter()

    def auto_refresh(self):
        if self.is_fetching:
            return True

        if self.check_adb_device():
            threading.Thread(target=self.fetch_apps_worker, daemon=True).start()
        else:
            GLib.idle_add(self.show_no_device_screen)

        return True

    def check_adb_device(self):
        try:
            output = subprocess.check_output(["adb", "get-state"], text=True, stderr=subprocess.STDOUT)
            return "device" in output
        except:
            return False


    def load_adb_apps(self):
        threading.Thread(target=self.fetch_apps_worker, daemon=True).start()

    def get_app_label(self, package_name):
        if package_name in self.labels_cache:
            return self.labels_cache[package_name]

        label = self.get_app_label_from_bridge(package_name)

        if not label:
            try:
                label = subprocess.check_output(
                    ["adb", "shell", f"cmd package get-app-label {package_name}"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
            except Exception:
                label = package_name

        self.labels_cache[package_name] = label
        return label

    def get_bridge_apk_path(self):
        flatpak_path = "/app/share/adbgui/bridge.apk"

        # Путь для разработки вне Flatpak
        local_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', 'data', 'bin', 'bridge.apk'
        ))

        return flatpak_path if os.path.exists(flatpak_path) else local_path

    def ensure_bridge_installed(self):
        try:
            res = subprocess.run(["adb", "shell", "pm", "list", "packages", "com.adbgui.bridge"],
                               capture_output=True, text=True)
            if "com.adbgui.bridge" not in res.stdout:
                apk = self.get_bridge_apk_path()
                if os.path.exists(apk):
                    subprocess.run(["adb", "install", "-r", "-g", apk], check=True)

        except Exception as e:
            print(f"Не удалось установить мост: {e}")

    def get_app_label_from_bridge(self, package_name):
        uri = f"content://com.adbgui.bridge/package/{package_name}"
        cmd = ["adb", "shell", "content", "query", "--uri", uri]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            output = result.stdout.strip()

            if "label=" in output:
                label = output.split("label=")[1].strip().strip("'").strip('"')
                if label and label != "null":
                    return label
        except Exception:
            pass
        return None

    def preload_all_labels(self):
        def bg_worker():
            uri = "content://com.adbgui.bridge/all"
            cmd = ["adb", "shell", "content", "query", "--uri", uri]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.splitlines():
                        if "package=" in line and "label=" in line:
                            parts = line.split(",")
                            pkg = next((p.split("=")[1].strip() for p in parts if "package=" in p), "")
                            lbl = next((p.split("=")[1].strip().strip("'\"") for p in parts if "label=" in p), "")

                            if pkg and lbl and lbl.lower() != "null":
                                self.labels_cache[pkg] = lbl

                    GLib.idle_add(self.refresh_visible_titles)
            except Exception as e:
                print(f"Preload failed: {e}")

        threading.Thread(target=bg_worker, daemon=True).start()

    def refresh_visible_titles(self):
        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            row = lst.get_first_child()
            while row:
                if hasattr(row, 'package_name'):
                    new_name = self.labels_cache.get(row.package_name)
                    if new_name and row.get_title() != new_name:
                        row.set_title(new_name)
                row = row.get_next_sibling()

    def update_row_title(self, package_name, new_title):
        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off]:
            row = lst.get_first_child()
            while row:
                if hasattr(row, 'package_name') and row.package_name == package_name:
                    row.set_title(new_title)
                row = row.get_next_sibling()

    def fetch_apps_worker(self):
        if self.is_fetching: return
        self.is_fetching = True

        try:
            self.ensure_bridge_installed()

            if not self.labels_cache:
                self.preload_all_labels()

            out = subprocess.check_output(["adb", "shell", "pm", "list", "packages", "-f", "-u"],
                                         text=True, timeout=3)

            off_out = subprocess.check_output(["adb", "shell", "pm", "list", "packages", "-d"],
                                             text=True, timeout=3)
            off_pkgs = {line.replace("package:", "").strip() for line in off_out.splitlines()}

            apps_data = []
            for line in out.splitlines():
                if "=" not in line: continue
                path_part, pkg_id = line.replace("package:", "").rsplit("=", 1)

                display_name = self.labels_cache.get(pkg_id, pkg_id)

                apps_data.append({
                    'title': display_name,
                    'id': pkg_id,
                    'is_off': pkg_id in off_pkgs,
                    'is_system': not path_part.startswith("/data/"),
                    'is_user': path_part.startswith("/data/")
                })

            apps_data.sort(key=lambda x: (x['is_system'], x['title'].lower()))
            GLib.idle_add(self.apply_apps_to_ui, apps_data)

        except subprocess.TimeoutExpired:
            print("ADB не ответил вовремя, пропускается цикл обновления")
        except Exception as e:
            print(f"Ошибка воркера: {e}")
        finally:
            self.is_fetching = False

    def apply_apps_to_ui(self, apps_data):
        has_apps = self.apps_list.get_first_child() is not None

        if not has_apps:
            self.status_stack.set_visible_child_name("page_list")
            for app in apps_data:
                self.add_row_to_correct_list(
                    app['title'], app['id'], app['is_off'], app['is_system'], app['is_user']
                )
            return

        if self.needs_full_reload or len(apps_data) != self.last_apps_count:
            self.clear_all_lists()
            for app in apps_data:
                self.add_row_to_correct_list(app['title'], app['id'], app['is_off'], app['is_system'], app['is_user'])
            self.needs_full_reload = False
        else:
            self.sync_existing_rows(apps_data)

        self.last_apps_count = len(apps_data)

    def sync_existing_rows(self, apps_data):
        data_map = {app['id']: app for app in apps_data}

        row = self.apps_list.get_first_child()
        while row:
            if hasattr(row, 'package_name'):
                pkg_id = row.package_name
                if pkg_id in data_map:
                    new_status = data_map[pkg_id]['is_off']
                    if row.is_off != new_status:
                        row.is_off = new_status
                        row.update_button_style()
            row = row.get_next_sibling()

    def show_no_device_screen(self):
            self.clear_all_lists()
            self.status_stack.set_visible_child_name("page_error")

    def clear_all_lists(self):
        for lst in [self.apps_list, self.page_apps_system, self.page_apps_off, self.page_apps_user]:
            lst.set_visible(False)
            while child := lst.get_first_child():
                lst.remove(child)
            lst.set_visible(True)

    def add_row_to_correct_list(self, title, pkg_id, is_off, is_system, is_user):
        new_row = AppRow(title, pkg_id, is_off=is_off, is_system=is_system)

        exists_in_all = False
        row = self.apps_list.get_first_child()
        while row:
            if hasattr(row, 'package_name') and row.package_name == pkg_id:
                row.is_off = is_off
                row.update_button_style()
                exists_in_all = True
                break
            row = row.get_next_sibling()

        if not exists_in_all:
            self.apps_list.append(AppRow(title, pkg_id, is_off=is_off, is_system=is_system))

        if is_off:
            self.page_apps_off.append(new_row)
            self._refresh_list_state(self.page_apps_off)
        else:
            target = self.page_apps_system if is_system else self.page_apps_user
            target.append(new_row)
            self._refresh_list_state(target)

        self._refresh_list_state(self.apps_list)

    def run_adb_command(self, args):
        import subprocess
        try:
            command = ["adb"] + args
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"error: {result.stderr.strip()}"
        except Exception as e:
            return f"failed: {str(e)}"


