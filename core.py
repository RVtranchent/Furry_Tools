"""Fenêtre principale (logo flottant) de Furry Tools."""
import os
import sys
import time
import shutil
import zipfile
import subprocess
import threading
import traceback

from PyQt5.QtCore import Qt, QPoint, QUrl, QSize, QTimer
from PyQt5.QtGui import QPixmap, QDesktopServices, QMovie, QColor
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QMessageBox,
                             QAction, QDialog, QFileDialog, QProgressDialog)

from config import (CONFIG_DIR, CACHE_FILE, DISCORD_CLIENT_ID, DISCORD_INVITE,
                    REPO_URL, load_config, save_config, load_cache, save_cache)
from themes import get_theme, get_all_themes, THEME_CATEGORIES
from themes_loader import (ensure_themes_dir, load_custom_themes, import_theme_file,
                           THEMES_DIR)
from icons import IconRenderer
from threads import (SteamPathDetector, NameFetcher, GameDLCDownloadThread,
                     ZipExtractThread)
from widgets import GameGridMenu
from dialogs import (SearchDialog, DLCSearchDialog, SettingsDialog,
                     ProfileCreationDialog, CreditsDialog, ThemeEditorDialog)
from tutorial import TutorialDialog
from plugins_loader import load_plugins, ensure_plugins_dir, PLUGINS_DIR

try:
    from pypresence import Presence
    PPRESENCE_AVAILABLE = True
except ImportError:
    PPRESENCE_AVAILABLE = False


class FurryTools(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.steam_folder = None
        self.steam_path = None
        self.target_folder = None
        self.movie = None
        self.game_names = load_cache()
        self.name_fetcher = None
        self.file_map = {}
        self.discord_rpc_thread = None
        self.discord_rpc_active = False
        self.tutorial_dialog = None
        self.drag_position = None
        self._plugins = []
        self._custom_themes = {}

        ensure_plugins_dir()
        ensure_themes_dir()
        self._custom_themes = load_custom_themes()
        self._plugins = load_plugins(self)   # charger AVANT _build_ui / _build_menu
        self._build_ui()
        self.start_discord_rpc_if_enabled()
        QTimer.singleShot(100, self._detect_steam_async)
        QTimer.singleShot(800, self.check_first_launch_tutorial)

    # ------------------------------------------------------------------
    def _menu_style(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        fs = max(10, self.config.get('font_size', 10))
        ff = self.config.get('font_family', 'Segoe UI')
        return f"""
            QMenu {{
                background-color:{t['bg_primary']}; color:{t['text_primary']};
                border:2px solid {t['border']}; border-radius:10px; padding:5px 0px;
                font-size:{fs}px; font-family:'{ff}';
            }}
            QMenu::item {{
                background:transparent; padding:8px 25px; margin:2px 5px;
                border-radius:5px; color:{t['text_primary']};
            }}
            QMenu::item:selected {{ background-color:{t['bg_secondary']}; }}
            QMenu::item:disabled {{ color:{t['text_secondary']}; }}
            QMenu::separator {{ height:1px; background-color:{t['border']}; margin:5px 10px; }}
        """

    def _build_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        size = self.config.get('icon_size', 150)
        self.setFixedSize(size, size)
        self.logo_label = QLabel(self)
        self.logo_label.setScaledContents(True)
        self.logo_label.setGeometry(0, 0, size, size)
        self._load_logo()
        self.setAcceptDrops(True)
        self._build_menu()

    def _build_menu(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        ic = t['text_primary']
        style = self._menu_style()
        self.context_menu = QMenu(self)
        self.context_menu.setStyleSheet(style)

        # --- Jeux & Profil ---
        self.jeux_menu = self.context_menu.addMenu("Jeux")
        self.jeux_menu.setStyleSheet(style)
        self.jeux_menu.aboutToShow.connect(self._safe_populate_jeux)

        self.profile_menu = self.context_menu.addMenu("Profil")
        self.profile_menu.setStyleSheet(style)
        self.profile_menu.aboutToShow.connect(self._populate_profile)

        self.context_menu.addSeparator()

        # --- Recherche ---
        search = self.context_menu.addAction("Rechercher un jeu Steam")
        search.setIcon(IconRenderer.icon('mouse', 20, QColor(ic)))
        search.triggered.connect(self.open_search_dialog)

        dlc = self.context_menu.addAction("Rechercher des DLC")
        dlc.setIcon(IconRenderer.icon('download', 20, QColor(ic)))
        dlc.triggered.connect(self.open_dlc_search_dialog)

        self.context_menu.addSeparator()

        # --- Steam (action dynamique) ---
        self.restart_action = self.context_menu.addAction("Redémarrer Steam")
        self.restart_action.setIcon(IconRenderer.icon('arrow_right', 20, QColor(ic)))
        self.restart_action.triggered.connect(self.restart_steam)

        self.context_menu.addSeparator()

        # --- Themes (menu compact : catégories + thèmes perso) ---
        themes_menu = self.context_menu.addMenu("Themes")
        themes_menu.setStyleSheet(style)
        current_theme = self.config.get('theme', 'Violet profond')

        cur_act = themes_menu.addAction("Actuel : " + current_theme)
        cur_act.setEnabled(False)
        themes_menu.addSeparator()

        # Thèmes intégrés, regroupés par famille pour ne pas surcharger le menu
        builtin_menu = themes_menu.addMenu("Thèmes intégrés")
        builtin_menu.setStyleSheet(style)
        for category, names in THEME_CATEGORIES.items():
            cat_menu = builtin_menu.addMenu(category)
            cat_menu.setStyleSheet(style)
            for theme_name in names:
                act = cat_menu.addAction(theme_name)
                act.setCheckable(True)
                act.setChecked(theme_name == current_theme)
                act.triggered.connect(
                    lambda checked=False, n=theme_name: self._apply_theme(n))

        # Thèmes personnalisés de l'utilisateur
        my_menu = themes_menu.addMenu("Mes thèmes")
        my_menu.setStyleSheet(style)
        if self._custom_themes:
            for theme_name in self._custom_themes:
                act = my_menu.addAction(theme_name)
                act.setCheckable(True)
                act.setChecked(theme_name == current_theme)
                act.triggered.connect(
                    lambda checked=False, n=theme_name: self._apply_theme(n))
        else:
            empty = my_menu.addAction("Aucun thème personnalisé")
            empty.setEnabled(False)

        themes_menu.addSeparator()
        manage_th = themes_menu.addAction("Gérer les thèmes...")
        manage_th.setIcon(IconRenderer.icon('clipboard', 18, QColor(ic)))
        manage_th.triggered.connect(self._open_theme_manager)
        create_th = themes_menu.addAction("Créer un thème...")
        create_th.setIcon(IconRenderer.icon('paw', 18, QColor(ic)))
        create_th.triggered.connect(self._open_theme_editor)
        themes_menu.addSeparator()
        reload_th = themes_menu.addAction("Recharger les thèmes")
        reload_th.setIcon(IconRenderer.icon('arrow_right', 18, QColor(ic)))
        reload_th.triggered.connect(self._reload_themes)
        themes_menu.addAction("Ouvrir le dossier themes").triggered.connect(
            self._open_themes_folder)

        # --- Paramètres ---
        self.context_menu.addAction("Paramètres").triggered.connect(self.open_settings)

        # --- Outils (sous-menu) ---
        outils = self.context_menu.addMenu("Outils")
        outils.setStyleSheet(style)
        outils.addAction("Extraire AppID du lien").triggered.connect(
            self.extract_appid_from_clipboard)
        outils.addSeparator()
        outils.addAction("Reset cache Steam").triggered.connect(self.reset_cache)
        outils.addAction("Vider le cache FurryTools").triggered.connect(self.clear_app_cache)
        outils.addSeparator()
        outils.addAction("Ouvrir le dossier des jeux").triggered.connect(self.open_target_folder)
        outils.addAction("Ouvrir le dossier cache").triggered.connect(self.open_cache_folder)
        outils.addAction("Downloads SteamTools").triggered.connect(self.download_steamtools)

        # --- Plugins ---
        plugins_menu = self.context_menu.addMenu("Plugins")
        plugins_menu.setStyleSheet(style)
        has_actions = False
        for plugin in self._plugins:
            for action in plugin["actions"]:
                plugins_menu.addAction(action)
                has_actions = True
        if not has_actions:
            none_action = plugins_menu.addAction("Aucun plugin chargé")
            none_action.setEnabled(False)
        plugins_menu.addSeparator()
        reload_act = plugins_menu.addAction("Recharger les plugins")
        reload_act.setIcon(IconRenderer.icon('arrow_right', 18, QColor(ic)))
        reload_act.triggered.connect(self._reload_plugins)
        guide_act = plugins_menu.addAction("Guide et exemples")
        guide_act.setIcon(IconRenderer.icon('book', 18, QColor(ic)))
        guide_act.triggered.connect(self._open_plugins_guide)
        plugins_menu.addAction("Ouvrir le dossier plugins").triggered.connect(
            self._open_plugins_folder)

        self.context_menu.addSeparator()

        # --- Aide ---
        tut = self.context_menu.addAction("Tutoriel")
        tut.setIcon(IconRenderer.icon('book', 20, QColor(ic)))
        tut.triggered.connect(self.show_tutorial)

        discord = self.context_menu.addAction("Project Lightning")
        discord.setIcon(IconRenderer.icon('chat', 20, QColor(ic)))
        discord.triggered.connect(self.open_discord)

        self.context_menu.addAction("Crédits").triggered.connect(self.show_credits)

        self.context_menu.addSeparator()

        # --- Quitter ---
        quit_action = self.context_menu.addAction("Quitter Furry Tools")
        quit_action.setIcon(IconRenderer.icon('close', 18, QColor(ic)))
        quit_action.triggered.connect(self.close_application)

    # ------------------------------------------------------------------
    def _detect_steam_async(self):
        self.detector = SteamPathDetector()
        self.detector.finished.connect(self._on_steam_detected)
        self.detector.start()

    def _on_steam_detected(self, folder, exe, target):
        self.steam_folder = folder
        self.steam_path = exe
        self.target_folder = target
        if folder is None:
            QTimer.singleShot(200, self._ask_steam_path)

    def _ask_steam_path(self):
        if QMessageBox.question(self, "Steam non trouvé",
                                "Impossible de trouver Steam.\nLe sélectionner manuellement ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier Steam")
            if folder and os.path.exists(os.path.join(folder, "steam.exe")):
                self.steam_folder = folder
                self.steam_path = os.path.join(folder, "steam.exe")
                self.target_folder = os.path.join(folder, "config", "stplug-in")

    # ---- Tutoriel ----
    def show_tutorial(self):
        try:
            if self.tutorial_dialog is not None:
                try:
                    self.tutorial_dialog.close()
                except Exception:
                    pass
            self.tutorial_dialog = TutorialDialog(self, self.config, main_window=self,
                                                   custom_themes=self._custom_themes)
            self.tutorial_dialog.show()
            self.tutorial_dialog.raise_()
            self.tutorial_dialog.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le tutoriel : {e}")
            traceback.print_exc()

    def check_first_launch_tutorial(self):
        if not self.config.get('tutorial_shown', False):
            self.show_tutorial()

    # ---- Dialogs ----
    def open_search_dialog(self):
        SearchDialog(self, self.config, self._custom_themes).exec_()

    def open_dlc_search_dialog(self):
        if not self.target_folder:
            QMessageBox.warning(self, "Erreur", "Le dossier Steam n'a pas été trouvé.")
            return
        DLCSearchDialog(self, self.config, self.target_folder, self._custom_themes).exec_()

    def open_settings(self):
        try:
            appids = []
            if self.target_folder and os.path.exists(self.target_folder):
                appids = [os.path.splitext(f)[0] for f in os.listdir(self.target_folder)
                          if f.lower().endswith('.lua')]
            dialog = SettingsDialog(self, self.config, appids, self.game_names, self._custom_themes)
            dialog.exec_()
            if dialog.result() == QDialog.Accepted:
                from utils import add_to_startup, remove_from_startup, is_in_startup
                new_config = dialog.get_updated_config()
                old_discord = self.config.get('enable_discord_rpc', False)
                new_discord = new_config.get('enable_discord_rpc', False)
                old_startup = is_in_startup()
                new_startup = new_config.get('start_with_windows', False)
                if new_startup and not old_startup:
                    add_to_startup()
                elif not new_startup and old_startup:
                    remove_from_startup()
                self.config = new_config
                save_config(self.config)
                size = self.config['icon_size']
                self.setFixedSize(size, size)
                self.logo_label.setGeometry(0, 0, size, size)
                self._load_logo()
                self._build_menu()  # reconstruire le menu avec le nouveau thème
                self.game_names.update(dialog.known_names)
                save_cache(self.game_names)
                if new_discord and not old_discord:
                    self.start_discord_rpc_if_enabled()
                elif not new_discord and old_discord:
                    self.stop_discord_rpc()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur paramètres : {e}")
            traceback.print_exc()

    def _populate_profile(self):
        self.profile_menu.clear()
        self.profile_menu.addAction("Créer un profil").triggered.connect(self.create_profile)
        self.profile_menu.addAction("Importer un profil").triggered.connect(self.import_profile)

    # ---- DLC ----
    def add_all_dlc_for_game(self, game_appid):
        if not self.target_folder:
            QMessageBox.warning(self, "Erreur", "Le dossier SteamTools n'existe pas.")
            return
        self.dlc_thread = GameDLCDownloadThread(game_appid, self.target_folder)
        self.pd = QProgressDialog("Récupération des DLC...", "Annuler", 0, 100, self)
        self.pd.setWindowModality(Qt.WindowModal)
        self.pd.setMinimumWidth(350)
        self.pd.canceled.connect(self.dlc_thread.cancel)
        self.dlc_thread.progress.connect(lambda v, m: (self.pd.setValue(v), self.pd.setLabelText(m)))
        self.dlc_thread.finished.connect(self._dlc_done)
        self.dlc_thread.error.connect(lambda e: (self.pd.close(), QMessageBox.critical(self, "Erreur", e)))
        self.dlc_thread.start()

    def _dlc_done(self, added, skipped, failed):
        self.pd.close()
        if added:
            msg = f"{len(added)} DLC ajoutés.\n"
            if skipped:
                msg += f"{len(skipped)} DLC déjà présents.\n"
            if failed:
                msg += f"{len(failed)} DLC en échec."
            QMessageBox.information(self, "Succès", msg)
        else:
            QMessageBox.information(self, "Info", "Aucun DLC trouvé pour ce jeu.")

    # ---- Logo ----
    def _load_logo(self):
        if self.movie is not None:
            self.movie.stop()
            self.movie = None
            self.logo_label.setMovie(None)
        path = self.config.get('logo_path', '')
        if path and os.path.exists(path):
            if path.lower().endswith('.gif'):
                self.movie = QMovie(path)
                self.movie.setScaledSize(QSize(self.width(), self.height()))
                self.logo_label.setMovie(self.movie)
                self.movie.start()
                return
            pix = QPixmap(path)
            if not pix.isNull():
                self.logo_label.setPixmap(pix)
                return
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        for p in (os.path.join(base, "logo.png"), os.path.join(os.getcwd(), "logo.png"),
                  os.path.join(CONFIG_DIR, "logo.png")):
            if os.path.exists(p):
                pix = QPixmap(p)
                if not pix.isNull():
                    self.logo_label.setPixmap(pix)
                    return
        # Logo par défaut : patte vectorielle
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        self.logo_label.setPixmap(IconRenderer.render('paw', self.width(), QColor(t['accent'])))

    # ---- Souris / menu ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            event.accept()

    def contextMenuEvent(self, event):
        try:
            if self.steam_path and os.path.exists(self.steam_path):
                self.restart_action.setText("Redémarrer Steam" if self.is_steam_running() else "Lancer Steam")
                self.restart_action.setEnabled(True)
            else:
                self.restart_action.setText("Steam non trouvé")
                self.restart_action.setEnabled(False)
            self.context_menu.exec_(event.globalPos())
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur menu : {e}")

    def is_steam_running(self):
        try:
            out = subprocess.check_output('tasklist /FI "IMAGENAME eq steam.exe"', shell=True, text=True)
            return "steam.exe" in out
        except Exception:
            return False

    # ---- Actions menu ----
    def open_discord(self):
        QDesktopServices.openUrl(QUrl(DISCORD_INVITE))

    def _apply_theme(self, name):
        self.config['theme'] = name
        save_config(self.config)
        self._build_menu()
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), f"Theme : {name}", self)

    def _reload_themes(self):
        self._custom_themes = load_custom_themes()
        self._build_menu()
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtGui import QCursor
        n = len(self._custom_themes)
        msg = f"{n} theme(s) personnalise(s) charge(s)" if n else "Aucun theme personnalise"
        QToolTip.showText(QCursor.pos(), msg, self)

    def _open_themes_folder(self):
        os.makedirs(THEMES_DIR, exist_ok=True)
        try:
            os.startfile(THEMES_DIR)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir : {e}")

    def _open_theme_editor(self):
        try:
            dlg = ThemeEditorDialog(self, self.config, self._custom_themes)
            if dlg.exec_() == QDialog.Accepted:
                self._custom_themes = load_custom_themes()
                self._build_menu()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir l'éditeur : {e}")
            traceback.print_exc()

    def _open_theme_manager(self):
        try:
            from dialogs import ThemeManagerDialog
            ThemeManagerDialog(self, self.config, self._custom_themes).exec_()
            # Le gestionnaire a pu supprimer/appliquer un thème : on resynchronise.
            self._custom_themes = load_custom_themes()
            self._build_menu()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le gestionnaire : {e}")
            traceback.print_exc()

    def _reload_plugins(self):
        from plugins_loader import load_plugins
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtGui import QCursor
        self._plugins = load_plugins(self)
        self._build_menu()
        n = len(self._plugins)
        msg = f"{n} plugin(s) recharge(s)" if n else "Aucun plugin trouve"
        QToolTip.showText(QCursor.pos(), msg, self)

    def _open_plugins_guide(self):
        try:
            from plugins_dialog import PluginsDialog
            PluginsDialog(self, self.config, self._plugins, self._custom_themes).exec_()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le guide : {e}")
            import traceback; traceback.print_exc()

    def _open_plugins_folder(self):
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        try:
            os.startfile(PLUGINS_DIR)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir : {e}")

    def show_credits(self):
        try:
            CreditsDialog(self, self.config, self._custom_themes).exec_()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir les crédits : {e}")
            import traceback; traceback.print_exc()

    def download_steamtools(self):
        QDesktopServices.openUrl(QUrl("https://www.steamtools.net/download"))

    def open_target_folder(self):
        if not self.target_folder:
            QMessageBox.warning(self, "Erreur", "Dossier Steam non trouvé")
            return
        try:
            os.makedirs(self.target_folder, exist_ok=True)
            os.startfile(self.target_folder)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir : {e}")

    def open_cache_folder(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.startfile(CONFIG_DIR)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir : {e}")

    def clear_app_cache(self):
        if QMessageBox.question(self, "Confirmation",
                                "Vider tout le cache des noms de jeux ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                if os.path.exists(CACHE_FILE):
                    os.remove(CACHE_FILE)
                self.game_names = {}
                QMessageBox.information(self, "Succès", "Cache vidé.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible : {e}")

    def extract_appid_from_clipboard(self):
        import re
        text = QApplication.clipboard().text()
        if not text:
            QMessageBox.warning(self, "Erreur", "Le presse-papiers est vide.")
            return
        m = re.search(r'\b(\d{1,10})\b', text)
        if m:
            QApplication.clipboard().setText(m.group(1))
            QMessageBox.information(self, "Succès", f"AppID {m.group(1)} copié.")
        else:
            QMessageBox.warning(self, "Erreur", "Aucun AppID trouvé dans le texte.")

    def delete_game(self, appid):
        try:
            fp = self.file_map.get(appid)
            if not fp or not os.path.exists(fp):
                QMessageBox.warning(self, "Erreur", "Fichier introuvable.")
                return
            if QMessageBox.question(self, "Confirmation", f"Supprimer {appid}.lua ?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                os.remove(fp)
                self.file_map.pop(appid, None)
                if appid in self.config['private_games']:
                    self.config['private_games'].remove(appid)
                    save_config(self.config)
                QMessageBox.information(self, "Succès", "Fichier supprimé.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible : {e}")

    def open_steamdb(self, appid):
        QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{appid}/"))

    # ---- Steam ----
    def restart_steam(self):
        if not self.steam_path or not os.path.exists(self.steam_path):
            QMessageBox.warning(self, "Erreur", "Steam non trouvé")
            return
        try:
            if self.is_steam_running():
                subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True)
                time.sleep(1)
            subprocess.Popen([self.steam_path])
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur : {e}")

    def reset_cache(self):
        if not self.steam_folder or not os.path.exists(self.steam_folder):
            QMessageBox.warning(self, "Erreur", "Steam non trouvé")
            return
        try:
            if self.is_steam_running():
                subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True)
                time.sleep(1)
            cleared = False
            for folder in ('appcache', 'depotcache'):
                fp = os.path.join(self.steam_folder, folder)
                if os.path.exists(fp):
                    for item in os.listdir(fp):
                        ip = os.path.join(fp, item)
                        if os.path.isfile(ip) or os.path.islink(ip):
                            os.unlink(ip)
                        elif os.path.isdir(ip):
                            shutil.rmtree(ip)
                    cleared = True
            subprocess.Popen([self.steam_path])
            QMessageBox.information(self, "Cache vidé" if cleared else "Info",
                                    "Caches Steam nettoyés." if cleared else "Aucun cache trouvé.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur : {e}")

    # ---- Profils ----
    def create_profile(self):
        if not self.target_folder or not os.path.exists(self.target_folder):
            QMessageBox.warning(self, "Erreur", "Dossier Steam non trouvé")
            return
        files = [f for f in os.listdir(self.target_folder) if f.lower().endswith('.lua')]
        if not files:
            QMessageBox.information(self, "Info", "Aucun fichier .lua trouvé.")
            return
        appids = {os.path.splitext(f)[0]: os.path.join(self.target_folder, f) for f in files}
        ProfileCreationDialog(self, appids, self.game_names).exec_()

    def import_profile(self):
        if not self.target_folder:
            QMessageBox.warning(self, "Erreur", "Dossier Steam non trouvé")
            return
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un profil",
            os.path.join(os.path.expanduser("~"), "Downloads"), "Fichiers ZIP (*.zip)")
        if not zip_path:
            return
        os.makedirs(self.target_folder, exist_ok=True)
        self.extract_thread = ZipExtractThread(zip_path, self.target_folder)
        self.pd = QProgressDialog("Import du profil...", "Annuler", 0, 100, self)
        self.pd.setWindowModality(Qt.WindowModal)
        self.pd.setMinimumWidth(350)
        self.extract_thread.progress.connect(self.pd.setValue)
        self.extract_thread.finished.connect(self._import_done)
        self.extract_thread.error.connect(lambda e: (self.pd.close(), QMessageBox.critical(self, "Erreur", e)))
        self.extract_thread.start()

    def _import_done(self, files):
        self.pd.close()
        if files:
            QMessageBox.information(self, "Succès", f"{len(files)} fichier(s) .lua importé(s).")
        else:
            QMessageBox.information(self, "Info", "Aucun fichier .lua dans l'archive.")

    # ---- Menu Jeux ----
    def _safe_populate_jeux(self):
        try:
            self._populate_jeux()
        except Exception:
            self.jeux_menu.clear()
            self.jeux_menu.addAction("Erreur de chargement").setEnabled(False)

    def _populate_jeux(self):
        self.jeux_menu.clear()
        if not self.target_folder or not os.path.exists(self.target_folder):
            self.jeux_menu.addAction("Dossier Steam introuvable").setEnabled(False)
            return
        files = [f for f in os.listdir(self.target_folder) if f.lower().endswith('.lua')]
        if not files:
            self.jeux_menu.addAction("Aucun jeu trouvé").setEnabled(False)
            return
        appids = [os.path.splitext(f)[0] for f in files]
        self.file_map = {a: os.path.join(self.target_folder, f) for a, f in zip(appids, files)}
        private = set(self.config.get('private_games', []))
        public = [a for a in appids if a not in private]
        priv = [a for a in appids if a in private]
        fs = self.config.get('font_size', 10)
        ff = self.config.get('font_family', 'Segoe UI')

        if public:
            pm = GameGridMenu("Public", self, self.config, self._custom_themes)
            for a in sorted(public):
                pm.add_game(a, self.game_names.get(a, a), self, fs, ff)
            pm.layout_games()
            self.jeux_menu.addMenu(pm)
        else:
            self.jeux_menu.addAction("Public (aucun)").setEnabled(False)

        if priv:
            prm = GameGridMenu("Privé", self, self.config, self._custom_themes)
            for a in sorted(priv):
                prm.add_game(a, self.game_names.get(a, a), self, fs, ff)
            prm.layout_games()
            self.jeux_menu.addMenu(prm)
        else:
            self.jeux_menu.addAction("Privé (aucun)").setEnabled(False)

        missing = [a for a in (set(public) | set(priv)) if a not in self.game_names]
        if missing:
            self._start_name_fetcher(missing)

    def _start_name_fetcher(self, appids):
        if self.name_fetcher and self.name_fetcher.isRunning():
            self.name_fetcher.quit()
            self.name_fetcher.wait(1000)
        self.name_fetcher = NameFetcher(appids)
        self.name_fetcher.names_ready.connect(self._on_names)
        self.name_fetcher.start()

    def _on_names(self, new_names):
        self.game_names.update(new_names)
        save_cache(self.game_names)

    # ---- Discord RPC ----
    def start_discord_rpc_if_enabled(self):
        if not PPRESENCE_AVAILABLE:
            return
        if self.config.get('enable_discord_rpc', False) and not self.discord_rpc_active:
            self.discord_rpc_active = True
            self.discord_rpc_thread = threading.Thread(target=self._discord_loop, daemon=True)
            self.discord_rpc_thread.start()

    def stop_discord_rpc(self):
        self.discord_rpc_active = False

    def _discord_loop(self):
        if not DISCORD_CLIENT_ID or len(DISCORD_CLIENT_ID) < 17 or not DISCORD_CLIENT_ID.isdigit():
            self.discord_rpc_active = False
            return
        try:
            rpc = Presence(DISCORD_CLIENT_ID)
            rpc.connect()
            start = int(time.time())
            while self.discord_rpc_active:
                rpc.update(state="Furry Tools", details="by rvmillions",
                           large_image="logo", large_text="Furry Tools", start=start,
                           buttons=[{"label": "Discord", "url": DISCORD_INVITE},
                                    {"label": "GitHub", "url": REPO_URL}])
                for _ in range(15):
                    if not self.discord_rpc_active:
                        break
                    time.sleep(1)
            rpc.close()
        except Exception:
            self.discord_rpc_active = False

    # ---- Drag & drop avec retour visuel (via bordure de fenêtre) ----
    def _set_drop_active(self, active):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        if active:
            self.logo_label.setStyleSheet(
                f"border:3px solid {t['border_focus']}; border-radius:12px; background-color: rgba(154,124,192,40);")
        else:
            self.logo_label.setStyleSheet("")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    p = url.toLocalFile().lower()
                    if p.endswith('.lua') or p.endswith('.zip') or p.endswith('.json'):
                        self._set_drop_active(True)
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        event.accept()

    def dropEvent(self, event):
        self._set_drop_active(False)
        # Trier les fichiers déposés : thèmes (.json) d'un côté, jeux (.lua/.zip) de l'autre
        theme_files, game_files = [], []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            fp = url.toLocalFile()
            lp = fp.lower()
            if lp.endswith('.json'):
                theme_files.append(fp)
            elif lp.endswith('.lua') or lp.endswith('.zip'):
                game_files.append(fp)

        if theme_files:
            self._import_dropped_themes(theme_files)
        if game_files:
            self._import_dropped_games(game_files)
        if not theme_files and not game_files:
            QMessageBox.information(self, "Info",
                                    "Aucun fichier reconnu (.lua, .zip ou .json).")

    def _import_dropped_themes(self, paths):
        """Importe des fichiers .json déposés comme thèmes personnalisés."""
        imported, errors = [], []
        for p in paths:
            ok, info = import_theme_file(p)
            if ok:
                imported.append(info)
            else:
                errors.append(f"{os.path.basename(p)} : {info}")
        if imported:
            self._custom_themes = load_custom_themes()
            self._build_menu()
        parts = []
        if imported:
            parts.append(f"{len(imported)} thème(s) importé(s) : " + ", ".join(imported))
            parts.append("Appliquez-le via clic droit > Themes > Mes thèmes.")
        if errors:
            parts.append("Erreurs :\n" + "\n".join(errors))
        if imported:
            QMessageBox.information(self, "Thèmes", "\n\n".join(parts))
        else:
            QMessageBox.warning(self, "Thèmes", "\n\n".join(parts) or "Aucun thème valide.")

    def _import_dropped_games(self, paths):
        """Copie/extrait les fichiers .lua et .zip déposés vers le dossier Steam."""
        if not self.target_folder:
            QMessageBox.warning(self, "Erreur", "Dossier Steam non trouvé")
            return
        try:
            os.makedirs(self.target_folder, exist_ok=True)
            copied, extracted = [], []
            for fp in paths:
                lp = fp.lower()
                if lp.endswith('.lua'):
                    shutil.copy(fp, self.target_folder)
                    copied.append(os.path.basename(fp))
                elif lp.endswith('.zip'):
                    with zipfile.ZipFile(fp, 'r') as zf:
                        for m in zf.namelist():
                            if m.lower().endswith('.lua'):
                                # Protection contre le path traversal dans les archives
                                safe_name = os.path.basename(m)
                                if not safe_name:
                                    continue
                                dest = os.path.join(self.target_folder, safe_name)
                                with zf.open(m) as src, open(dest, 'wb') as dst:
                                    dst.write(src.read())
                                extracted.append(safe_name)
            if copied or extracted:
                msg = ""
                if copied:
                    msg += f"{len(copied)} fichier(s) .lua copié(s).\n"
                if extracted:
                    msg += f"{len(extracted)} fichier(s) .lua extrait(s) du zip."
                QMessageBox.information(self, "Opération terminée", msg)
            else:
                QMessageBox.information(self, "Info", "Aucun fichier .lua trouvé.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du drop : {e}")

    # ---- Sortie ----
    def close_application(self):
        self.stop_discord_rpc()
        # Arrêter les threads en cours avant de quitter
        for attr in ('name_fetcher', 'detector'):
            th = getattr(self, attr, None)
            if th and hasattr(th, 'isRunning') and th.isRunning():
                if hasattr(th, 'cancel'):
                    th.cancel()
                th.quit()
                th.wait(800)
        from utils import release_instance_mutex
        release_instance_mutex()
        QApplication.quit()
