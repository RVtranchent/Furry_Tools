"""Threads asynchrones (appels réseau, zip) de Furry Tools."""
import os
import re
import json
import time
import shutil
import zipfile
import tempfile
import urllib.request
import urllib.parse

from PyQt5.QtCore import QThread, pyqtSignal

from config import VERSION_URL

UA = {'User-Agent': 'Mozilla/5.0'}


class GameDLCDownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list, list, list)
    error = pyqtSignal(str)

    def __init__(self, game_appid, target_folder):
        super().__init__()
        self.game_appid = str(game_appid)
        self.target_folder = target_folder
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        added, skipped, failed = [], [], []
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={self.game_appid}&l=french"
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            entry = data.get(self.game_appid, {})
            if entry.get('success') and entry['data'].get('dlc'):
                dlcs = entry['data']['dlc']
                total = len(dlcs)
                steamtools_file = os.path.join(self.target_folder, "Steamtools.lua")
                existing = []
                if os.path.exists(steamtools_file):
                    with open(steamtools_file, 'r', encoding='utf-8') as f:
                        existing = f.read().splitlines()
                for i, dlc_id in enumerate(dlcs):
                    if self._cancelled:
                        break
                    percent = int((i + 1) * 100 / total)
                    self.progress.emit(percent, f"Vérification DLC {dlc_id}...")
                    line = f"addappid({dlc_id}, 1)"
                    if line not in existing:
                        try:
                            with open(steamtools_file, 'a', encoding='utf-8') as f:
                                f.write(line + "\n")
                            existing.append(line)
                            added.append(str(dlc_id))
                        except Exception:
                            failed.append(str(dlc_id))
                    else:
                        skipped.append(str(dlc_id))
            self.finished.emit(added, skipped, failed)
        except Exception as e:
            self.error.emit(str(e))


class SteamDLCSearchThread(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        try:
            encoded = urllib.parse.quote(self.query)
            url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=french&cc=fr"
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            for item in data.get('items', []):
                if self._cancelled:
                    return
                if item.get('type') == 'dlc':
                    results.append({'appid': str(item['id']), 'name': item['name'], 'type': 'dlc'})
                elif item.get('type') == 'game':
                    appid = str(item['id'])
                    try:
                        dlc_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=french"
                        with urllib.request.urlopen(urllib.request.Request(dlc_url, headers=UA), timeout=3) as r:
                            dd = json.loads(r.read().decode())
                        if dd.get(appid, {}).get('success') and dd[appid]['data'].get('dlc'):
                            for dlc_id in dd[appid]['data']['dlc']:
                                results.append({'appid': str(dlc_id), 'name': f"DLC {dlc_id}", 'type': 'dlc'})
                    except Exception:
                        pass
        except Exception as e:
            self.error_occurred.emit(str(e))
            return
        if not self._cancelled:
            self.results_ready.emit(results)


class SteamSearchThread(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query):
        super().__init__()
        self.query = query
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        try:
            encoded = urllib.parse.quote(self.query)
            url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=english&cc=us"
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            for item in data.get('items', []):
                results.append({
                    'appid': str(item['id']),
                    'name': item['name'],
                    'price': item.get('price', {}).get('final_formatted', 'Gratuit'),
                    'type': item.get('type', 'game')
                })
        except Exception:
            pass
        if not self._cancelled:
            self.results_ready.emit(results)


class NameFetcher(QThread):
    names_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, appids):
        super().__init__()
        self.appids = appids

    def run(self):
        result = {}
        for appid in self.appids:
            if str(appid).isdigit():
                try:
                    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
                    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=5) as r:
                        data = json.loads(r.read().decode())
                    if data.get(appid, {}).get('success'):
                        result[appid] = data[appid]['data']['name']
                    else:
                        result[appid] = appid
                except Exception:
                    result[appid] = appid
            else:
                result[appid] = appid
        self.names_ready.emit(result)


class ZipCreationThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_paths, zip_name, download_folder):
        super().__init__()
        self.file_paths = file_paths
        self.zip_name = zip_name
        self.download_folder = download_folder

    def run(self):
        try:
            zip_path = os.path.join(self.download_folder, self.zip_name)
            total = max(1, len(self.file_paths))
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, fp in enumerate(self.file_paths):
                    if os.path.exists(fp):
                        zf.write(fp, os.path.basename(fp))
                    self.progress.emit(int((i + 1) / total * 100))
            self.finished.emit(zip_path)
        except Exception as e:
            self.error.emit(str(e))


class ZipExtractThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, zip_path, target_folder):
        super().__init__()
        self.zip_path = zip_path
        self.target_folder = target_folder

    def run(self):
        try:
            extracted = []
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                members = [m for m in zf.namelist() if m.lower().endswith('.lua')]
                total = max(1, len(members))
                for i, m in enumerate(members):
                    zf.extract(m, self.target_folder)
                    extracted.append(m)
                    self.progress.emit(int((i + 1) / total * 100))
            self.finished.emit(extracted)
        except Exception as e:
            self.error.emit(str(e))


class UpdateChecker(QThread):
    update_checked = pyqtSignal(bool, str, str)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            # Cache-buster : raw.githubusercontent.com peut servir une ancienne
            # version.txt depuis son CDN. On force une réponse fraîche.
            sep = '&' if '?' in VERSION_URL else '?'
            url = f"{VERSION_URL}{sep}_={int(time.time())}"
            headers = dict(UA)
            headers['Cache-Control'] = 'no-cache'
            headers['Pragma'] = 'no-cache'
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as r:
                latest = r.read().decode('utf-8-sig').strip()
            if not latest:
                raise ValueError("version.txt distant vide")
            self.update_checked.emit(self._newer(latest, self.current_version), latest, self.current_version)
        except Exception:
            # latest vide => signale un echec de verification (et non "a jour")
            self.update_checked.emit(False, "", self.current_version)

    @staticmethod
    def _newer(v1, v2):
        def parse(v):
            # Tolérant : ignore BOM/espaces et ne garde que les groupes de chiffres.
            return [int(n) for n in re.findall(r'\d+', v or '')]
        try:
            a, b = parse(v1), parse(v2)
            if not a:
                return False
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else 0
                y = b[i] if i < len(b) else 0
                if x > y:
                    return True
                if x < y:
                    return False
            return False
        except Exception:
            return False


class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url, save_path):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path

    def run(self):
        try:
            req = urllib.request.Request(self.download_url, headers=UA)
            with urllib.request.urlopen(req, timeout=10) as response:
                total = int(response.headers.get('content-length', 0))
                done = 0
                with open(self.save_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            self.progress.emit(int(done * 100 / total))
            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))


class UpdateInstaller(QThread):
    """Installe une mise a jour : extrait l'archive ZIP et remplace les
    fichiers de code dans le dossier de l'application.

    Les dossiers de donnees utilisateur (themes/, plugins/) ainsi que les
    dossiers techniques (.git, __pycache__...) sont preserves.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    SKIP_TOP = {'themes', 'plugins', '__pycache__', '.git', '.github', 'logs'}

    def __init__(self, zip_path, app_dir):
        super().__init__()
        self.zip_path = zip_path
        self.app_dir = app_dir

    def run(self):
        tmp = None
        try:
            tmp = tempfile.mkdtemp(prefix='ft_update_')
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                zf.extractall(tmp)

            # L'archive GitHub contient un dossier racine unique (ex: Furry_Tools-main)
            dirs = [os.path.join(tmp, e) for e in os.listdir(tmp)
                    if os.path.isdir(os.path.join(tmp, e))]
            src_root = dirs[0] if len(dirs) == 1 else tmp

            # Lister les fichiers a copier (hors dossiers proteges)
            files = []
            for dirpath, dirnames, filenames in os.walk(src_root):
                rel_dir = os.path.relpath(dirpath, src_root)
                top = '' if rel_dir == '.' else rel_dir.replace('\\', '/').split('/')[0]
                if top in self.SKIP_TOP:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d not in self.SKIP_TOP]
                for fn in filenames:
                    files.append(os.path.join(dirpath, fn))

            total = max(1, len(files))
            copied = 0
            for i, src in enumerate(files):
                rel = os.path.relpath(src, src_root)
                dest = os.path.join(self.app_dir, rel)
                os.makedirs(os.path.dirname(dest) or self.app_dir, exist_ok=True)
                shutil.copy2(src, dest)
                copied += 1
                self.progress.emit(int((i + 1) * 100 / total))

            self.finished.emit(f"{copied} fichier(s) mis a jour")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)


class SteamPathDetector(QThread):
    finished = pyqtSignal(object, object, object)

    def run(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            steam_path = steam_path.replace('/', '\\')
            if os.path.exists(os.path.join(steam_path, "steam.exe")):
                self.finished.emit(steam_path,
                                   os.path.join(steam_path, "steam.exe"),
                                   os.path.join(steam_path, "config", "stplug-in"))
                return
        except Exception:
            pass

        for path in [
            os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
            os.path.expandvars(r"%ProgramFiles%\Steam"),
            os.path.expandvars(r"%LOCALAPPDATA%\Steam"),
            "C:\\Program Files (x86)\\Steam",
            "C:\\Program Files\\Steam",
            "D:\\Steam", "E:\\Steam",
        ]:
            expanded = os.path.expandvars(path)
            if os.path.exists(os.path.join(expanded, "steam.exe")):
                self.finished.emit(expanded,
                                   os.path.join(expanded, "steam.exe"),
                                   os.path.join(expanded, "config", "stplug-in"))
                return
        self.finished.emit(None, None, None)
