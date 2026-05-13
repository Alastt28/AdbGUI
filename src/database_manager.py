import urllib.request, json, os, threading
from PySide6.QtCore import QObject, Signal
from pathlib import Path

class DatabaseManager(QObject):
    dbUpdated = Signal()

    def __init__(self):
        super().__init__()
        self.url = "https://raw.githubusercontent.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation/main/resources/assets/uad_lists.json"
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "adbgui")
        self.cache_path = os.path.join(self.cache_dir, "uad_lists.json")
        self.bundled_path = str(Path(__file__).parent.parent / "data" / "uad_lists.json")
        self.descriptions = {}

    def load_initial_data(self):
        if os.path.exists(self.cache_path):
            self._parse_json(self.cache_path)
            print("[UAD] Загружено из кэша")
        elif os.path.exists(self.bundled_path):
            print(f"[UAD] Кэша нет, но есть вшитый файл {self.bundled_path}")
            self._parse_json(self.bundled_path)
            print("[UAD] Загружено из папки data")
        else:
            print(f"[UAD] База не найдена ни в {self.cache_path}, ни в {self.bundled_path}")

    def sync_with_github(self):
        threading.Thread(target=self._download_task, daemon=True).start()

    def _download_task(self):
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AdbGUI/1.0'}

        # 1. HEAD-запрос для получения ETag
        try:
            req = urllib.request.Request(self.url, method='HEAD', headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                remote_etag = resp.headers.get('ETag')
                if not remote_etag:
                    print("[UAD] Сервер не предоставил ETag, выполняется полная загрузка.")
                    self._perform_full_download()
                    return
        except Exception as e:
            print(f"[UAD] Ошибка при HEAD-запросе: {e}. Выполняется полная загрузка.")
            self._perform_full_download()
            return

        local_etag = None
        if os.path.exists(self.cache_path):
            etag_file_path = self.cache_path + '.etag'
            if os.path.exists(etag_file_path):
                with open(etag_file_path, 'r') as f:
                    local_etag = f.read().strip()

        if remote_etag and local_etag == remote_etag:
            print("[UAD] Файл не изменился, обновление не требуется.")
            return

        print("[UAD] ETag изменился или отсутствует, выполняется загрузка...")
        self._perform_full_download()

    def _perform_full_download(self):
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AdbGUI/1.0'}
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
                print(f"[UAD] Директория кэша создана: {self.cache_dir}")

            print(f"[UAD] Начинается загрузка из {self.url}")
            req = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                new_data = response.read()
                new_etag = response.headers.get('ETag')
                print(f"[UAD] Скачано {len(new_data)} байт")

                with open(self.cache_path, 'wb') as f:
                    f.write(new_data)

                if new_etag:
                    etag_file_path = self.cache_path + '.etag'
                    with open(etag_file_path, 'w') as f:
                        f.write(new_etag)
                    print(f"[UAD] Сохранён новый ETag: {new_etag}")

                self._parse_json(self.cache_path)
                self.dbUpdated.emit()
                print("[UAD] База успешно обновлена из сети")

        except Exception as e:
            print(f"[UAD] Ошибка при полной загрузке: {e}")

    def _parse_json(self, path):
        try:
            print(f"[UAD] Парсинг JSON: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.descriptions = data
                    print(f"[UAD] Успешно распарсено {len(self.descriptions)} приложений")
                else:
                    self.descriptions = {}
                    print("[UAD] Ошибка парсинга словаря.")

        except Exception as e:
            print(f"[UAD] Ошибка парсинга JSON: {e}")
            self.descriptions = {}

    def get_info(self, package_id):
        return self.descriptions.get(package_id, {})