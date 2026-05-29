"""Boîtes de dialogue de Furry Tools (recherche, DLC, paramètres, profils)."""
import os
import re
import sys
import json
import shutil
import zipfile
import tempfile
import urllib.request
from datetime import datetime

from PyQt5.QtCore import Qt, QUrl, QSize, QTimer, QMimeData
from PyQt5.QtGui import (QColor, QCursor, QDesktopServices, QFont, QFontDatabase,
                         QPixmap, QDrag)
from PyQt5.QtWidgets import (QApplication, QColorDialog, QDialog, QFrame, QWidget,
                             QLabel, QMenu, QMessageBox, QAction, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QSlider, QSpinBox,
                             QListWidget, QListWidgetItem, QCheckBox, QLineEdit,
                             QPushButton, QGroupBox, QFileDialog, QProgressDialog,
                             QProgressBar, QComboBox, QTabWidget, QScrollArea,
                             QSizePolicy)

from themes import THEMES, get_theme, get_all_themes, get_theme_stylesheet
from icons import IconRenderer
from utils import center_window, get_scaled_size, is_in_startup
from config import (CONFIG_DIR, CACHE_FILE, CURRENT_VERSION, REPO_URL,
                    DISCORD_INVITE, UPDATE_ZIP_URL, APP_DIR, save_config)
from threads import (GameDLCDownloadThread, SteamDLCSearchThread, SteamSearchThread,
                     NameFetcher, ZipCreationThread, UpdateChecker, UpdateDownloader,
                     UpdateInstaller)

try:
    import pypresence  # noqa
    PPRESENCE_AVAILABLE = True
except ImportError:
    PPRESENCE_AVAILABLE = False


def _list_style(t):
    return f"""
        QListWidget {{
            background-color:{t['bg_secondary']}; color:{t['text_primary']};
            border:1px solid {t['border']}; border-radius:4px; padding:4px; outline:none;
        }}
        QListWidget::item {{
            padding:8px; border-bottom:1px solid {t['border']};
            color:{t['text_primary']}; background-color:{t['bg_secondary']};
        }}
        QListWidget::item:selected {{ background-color:{t['accent']}; color:{t['text_primary']}; }}
        QListWidget::item:hover {{ background-color:{t['accent_hover']}; }}
    """


class SelectGameForDLCDialog(QDialog):
    def __init__(self, parent, config, target_folder, games_with_dlc_status, game_names,
                 custom_themes=None):
        super().__init__(parent)
        self.config = config
        self._custom_themes = custom_themes or {}
        self.target_folder = target_folder
        self.games_with_dlc_status = games_with_dlc_status
        self.game_names = game_names
        self.selected_games = []
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setWindowTitle("Sélectionner les jeux pour ajouter les DLC")
        self.setModal(True)
        w, h = get_scaled_size(600, 500)
        self.resize(w, h)
        self._build()
        center_window(self)

    def _build(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        info = QLabel("Sélectionnez les jeux pour lesquels ajouter les DLC manquants :")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.games_list = QListWidget()
        self.games_list.setSelectionMode(QListWidget.MultiSelection)
        self.games_list.setStyleSheet(_list_style(t))
        for appid, (name, missing) in self.games_with_dlc_status.items():
            item = QListWidgetItem(f"{name} (APPID: {appid}) — {missing} DLC manquant(s)")
            item.setData(Qt.UserRole, appid)
            self.games_list.addItem(item)
        layout.addWidget(self.games_list)
        sel = QHBoxLayout()
        a = QPushButton("Tout sélectionner")
        a.clicked.connect(self.games_list.selectAll)
        d = QPushButton("Tout désélectionner")
        d.clicked.connect(self.games_list.clearSelection)
        sel.addStretch()
        sel.addWidget(a)
        sel.addWidget(d)
        sel.addStretch()
        layout.addLayout(sel)
        btns = QHBoxLayout()
        ok = QPushButton("Ajouter les DLC sélectionnés")
        ok.clicked.connect(self._confirm)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _confirm(self):
        self.selected_games = [i.data(Qt.UserRole) for i in self.games_list.selectedItems()]
        if not self.selected_games:
            QMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner au moins un jeu.")
            return
        self.accept()


class DLCSearchDialog(QDialog):
    def __init__(self, parent, config, target_folder, custom_themes=None):
        super().__init__(parent)
        self.config = config
        self._custom_themes = custom_themes or {}
        self.target_folder = target_folder
        self.search_thread = None
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setWindowTitle("Recherche de DLC")
        self.setModal(True)
        w, h = get_scaled_size(700, 600)
        self.resize(w, h)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_search)
        self._build()
        center_window(self)

    def _build(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        grp = QGroupBox("Recherche")
        gl = QHBoxLayout(grp)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tapez le nom d'un jeu ou d'un DLC...")
        self.search_input.textChanged.connect(lambda: self._debounce.start(300))
        gl.addWidget(self.search_input)
        layout.addWidget(grp)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        rgrp = QGroupBox("Résultats")
        rl = QVBoxLayout(rgrp)
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(_list_style(t))
        self.results_list.itemDoubleClicked.connect(self._on_dbl)
        rl.addWidget(self.results_list)
        layout.addWidget(rgrp)
        info = QLabel("Double-cliquez sur un DLC pour l'ajouter au fichier Steamtools.lua")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

    def _do_search(self):
        text = self.search_input.text()
        if len(text) < 2:
            self.results_list.clear()
            self.status_label.setText("")
            return
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.quit()
            self.search_thread.wait(800)
        self.status_label.setText("Recherche en cours...")
        self.search_thread = SteamDLCSearchThread(text)
        self.search_thread.results_ready.connect(self._show_results)
        self.search_thread.error_occurred.connect(lambda m: self.status_label.setText(f"Erreur : {m}"))
        self.search_thread.start()

    def _show_results(self, results):
        self.results_list.clear()
        if not results:
            self.status_label.setText("Aucun DLC trouvé. Essayez un autre terme.")
            return
        self.status_label.setText(f"{len(results)} DLC trouvé(s).")
        for dlc in results:
            item = QListWidgetItem(f"{dlc['name']} (APPID: {dlc['appid']})")
            item.setData(Qt.UserRole, dlc)
            self.results_list.addItem(item)

    def closeEvent(self, event):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.quit()
            self.search_thread.wait(500)
        super().closeEvent(event)

    def _on_dbl(self, item):
        dlc = item.data(Qt.UserRole)
        if not dlc:
            return
        if not self.target_folder or not os.path.exists(self.target_folder):
            QMessageBox.warning(self, "Erreur", "Le dossier SteamTools n'existe pas.\nInstallez SteamTools d'abord.")
            return
        steamtools_file = os.path.join(self.target_folder, "Steamtools.lua")
        appid = dlc['appid']
        existing = []
        if os.path.exists(steamtools_file):
            with open(steamtools_file, 'r', encoding='utf-8') as f:
                existing = f.read().splitlines()
        line = f"addappid({appid}, 1)"
        if line in existing:
            QMessageBox.information(self, "Déjà présent", f"Le DLC {dlc['name']} (APPID: {appid}) est déjà présent.")
            return
        try:
            with open(steamtools_file, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
            QMessageBox.information(self, "Succès", f"DLC ajouté avec succès !\n{line}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'écrire dans le fichier : {e}")


class SearchDialog(QDialog):
    def __init__(self, parent, config, custom_themes=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = config
        self._custom_themes = custom_themes or {}
        self.search_thread = None
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setWindowTitle("Recherche de jeux Steam")
        self.setModal(True)
        w, h = get_scaled_size(600, 500)
        self.resize(w, h)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_search)
        self._build()
        center_window(self)

    def _build(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tapez le nom d'un jeu (les espaces sont acceptés)...")
        self.search_input.textChanged.connect(lambda: self._debounce.start(300))
        layout.addWidget(self.search_input)
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setStyleSheet(_list_style(t))
        self.results_list.itemDoubleClicked.connect(self._on_dbl)
        layout.addWidget(self.results_list)
        info = QLabel("Double-cliquez sur un jeu pour voir les options")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

    def _do_search(self):
        text = self.search_input.text()
        if len(text) < 3:
            self.results_list.clear()
            return
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.quit()
            self.search_thread.wait(800)
        self.search_thread = SteamSearchThread(text)
        self.search_thread.results_ready.connect(self._show_results)
        self.search_thread.start()

    def _show_results(self, results):
        self.results_list.clear()
        if not results:
            item = QListWidgetItem("Aucun résultat trouvé")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.results_list.addItem(item)
            return
        for game in results:
            item = QListWidgetItem(f"{game['name']} (APPID: {game['appid']})")
            item.setData(Qt.UserRole, game)
            self.results_list.addItem(item)

    def _on_dbl(self, item):
        game = item.data(Qt.UserRole)
        if not game:
            return
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color:{t['bg_primary']}; color:{t['text_primary']};
                     border:2px solid {t['border']}; border-radius:6px; padding:5px; }}
            QMenu::item {{ padding:6px 15px; border-radius:3px; }}
            QMenu::item:selected {{ background-color:{t['bg_secondary']}; }}
        """)
        a1 = QAction("Copier l'APPID", menu)
        a1.setIcon(IconRenderer.icon('copy', 18, t['text_primary']))
        a1.triggered.connect(lambda: self._copy(game['appid'], f"APPID {game['appid']} copié"))
        menu.addAction(a1)
        a2 = QAction("Copier la commande /gen", menu)
        a2.setIcon(IconRenderer.icon('clipboard', 18, t['text_primary']))
        a2.triggered.connect(lambda: self._copy(f"/gen appid:{game['appid']}", f"Commande /gen appid:{game['appid']} copiée"))
        menu.addAction(a2)
        a3 = QAction("Ouvrir dans SteamDB", menu)
        a3.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://steamdb.info/app/{game['appid']}/")))
        menu.addAction(a3)
        if self.config.get('auto_add_all_dlc', False) and self.parent_window:
            a4 = QAction("Ajouter tous les DLC", menu)
            a4.triggered.connect(lambda: self.parent_window.add_all_dlc_for_game(game['appid']))
            menu.addAction(a4)
        menu.exec_(QCursor.pos())

    def closeEvent(self, event):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.search_thread.quit()
            self.search_thread.wait(500)
        super().closeEvent(event)

    def _copy(self, text, msg):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copié", msg)


class ProfileCreationDialog(QDialog):
    def __init__(self, parent, appids_with_paths, known_names):
        super().__init__(parent)
        self.appids_with_paths = appids_with_paths
        self.known_names = known_names
        self.config = getattr(parent, 'config', {}) or {}
        self._custom_themes = getattr(parent, '_custom_themes', {}) or {}
        self.setWindowTitle("Créer un profil")
        self.setModal(True)
        self.resize(self.config.get('dialog_width', 500), self.config.get('dialog_height', 550))
        self.setStyleSheet(get_theme_stylesheet(self.config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self._build()
        center_window(self)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        label = QLabel("Sélectionnez les jeux à inclure dans le profil :")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.games_list = QListWidget()
        self.games_list.setSelectionMode(QListWidget.NoSelection)
        for appid in sorted(self.appids_with_paths):
            item = QListWidgetItem(self.known_names.get(appid, appid))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, appid)
            self.games_list.addItem(item)
        layout.addWidget(self.games_list)
        sel = QHBoxLayout()
        a = QPushButton("Tout sélectionner")
        a.clicked.connect(lambda: self._set_all(Qt.Checked))
        d = QPushButton("Tout désélectionner")
        d.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        sel.addStretch()
        sel.addWidget(a)
        sel.addWidget(d)
        sel.addStretch()
        layout.addLayout(sel)
        btns = QHBoxLayout()
        create = QPushButton("Créer")
        create.clicked.connect(self._create)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(create)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _set_all(self, state):
        for i in range(self.games_list.count()):
            self.games_list.item(i).setCheckState(state)

    def _create(self):
        selected = [self.games_list.item(i).data(Qt.UserRole)
                    for i in range(self.games_list.count())
                    if self.games_list.item(i).checkState() == Qt.Checked]
        if not selected:
            QMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner au moins un jeu.")
            return
        paths = [self.appids_with_paths[a] for a in selected if a in self.appids_with_paths]
        if not paths:
            QMessageBox.warning(self, "Erreur", "Aucun fichier trouvé.")
            return
        zip_name = f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        self.thread = ZipCreationThread(paths, zip_name, downloads)
        self.pd = QProgressDialog("Création du profil...", "Annuler", 0, 100, self)
        self.pd.setWindowModality(Qt.WindowModal)
        self.pd.setMinimumWidth(350)
        self.thread.progress.connect(self.pd.setValue)
        self.thread.finished.connect(self._done)
        self.thread.error.connect(self._err)
        self.thread.start()

    def _done(self, path):
        self.pd.close()
        QMessageBox.information(self, "Succès", f"Profil créé :\n{path}")
        self.accept()

    def _err(self, msg):
        self.pd.close()
        QMessageBox.critical(self, "Erreur", f"Échec :\n{msg}")


class SettingsDialog(QDialog):
    def __init__(self, parent, config, all_appids, known_names, custom_themes=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = config.copy()
        self._custom_themes = custom_themes or {}
        self.all_appids = all_appids
        self.known_names = known_names.copy()
        self.game_names = known_names.copy()
        self.name_fetcher = None
        self.update_checker = None
        self.update_downloader = None
        self.latest_version = None
        self.resize(config.get('dialog_width', 600), config.get('dialog_height', 600))
        self.setWindowTitle("Paramètres")
        self.setModal(True)
        self._build()
        self._fetch_missing()
        center_window(self)

    def _build(self):
        self.setStyleSheet(get_theme_stylesheet(self.config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(10, 10, 10, 10)
        tabs = QTabWidget()

        # ---------- Onglet Général ----------
        general = QWidget()
        gl = QVBoxLayout(general)
        gl.setSpacing(10)

        size_grp = QGroupBox("Taille du logo")
        sl = QHBoxLayout(size_grp)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(50, 300)
        self.size_slider.setValue(self.config['icon_size'])
        self.size_spin = QSpinBox()
        self.size_spin.setRange(50, 300)
        self.size_spin.setValue(self.config['icon_size'])
        self.size_slider.valueChanged.connect(self.size_spin.setValue)
        self.size_spin.valueChanged.connect(self.size_slider.setValue)
        sl.addWidget(self.size_slider)
        sl.addWidget(self.size_spin)
        gl.addWidget(size_grp)

        font_grp = QGroupBox("Police d'écriture")
        fl = QGridLayout(font_grp)
        fl.addWidget(QLabel("Famille :"), 0, 0)
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(QFontDatabase().families())
        idx = self.font_family_combo.findText(self.config.get('font_family', 'Segoe UI'))
        if idx >= 0:
            self.font_family_combo.setCurrentIndex(idx)
        fl.addWidget(self.font_family_combo, 0, 1, 1, 2)
        fl.addWidget(QLabel("Taille :"), 1, 0)
        self.font_size_slider = QSlider(Qt.Horizontal)
        self.font_size_slider.setRange(8, 16)
        self.font_size_slider.setValue(self.config.get('font_size', 10))
        fl.addWidget(self.font_size_slider, 1, 1)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setValue(self.config.get('font_size', 10))
        self.font_size_slider.valueChanged.connect(self.font_size_spin.setValue)
        self.font_size_spin.valueChanged.connect(self.font_size_slider.setValue)
        fl.addWidget(self.font_size_spin, 1, 2)
        fl.addWidget(QLabel("Aperçu :"), 2, 0)
        self.preview_text = QLabel("Furry Tools - Jeux")
        self.preview_text.setStyleSheet(f"background-color:{t['bg_secondary']}; padding:4px; border-radius:3px;")
        fl.addWidget(self.preview_text, 2, 1, 1, 2)
        self.font_family_combo.currentTextChanged.connect(self._update_preview)
        self.font_size_slider.valueChanged.connect(self._update_preview)
        gl.addWidget(font_grp)

        theme_grp = QGroupBox("Theme actif")
        tl = QHBoxLayout(theme_grp)
        current = self.config.get('theme', 'Violet profond')
        theme_lbl = QLabel(f"<b>{current}</b>")
        theme_lbl.setStyleSheet("font-size:11px;")
        tl.addWidget(theme_lbl)
        tl.addStretch()
        hint = QLabel("Clic droit sur le logo > Themes pour changer")
        hint.setStyleSheet(f"color:{t['text_secondary']}; font-size:9px; font-style:italic;")
        tl.addWidget(hint)
        gl.addWidget(theme_grp)

        logo_grp = QGroupBox("Logo personnalisé")
        ll = QVBoxLayout(logo_grp)
        self.logo_label = QLabel()
        self._update_logo_display()
        ll.addWidget(self.logo_label)
        change = QPushButton("Changer le logo...")
        change.clicked.connect(self._change_logo)
        ll.addWidget(change)
        reset = QPushButton("Restaurer le logo par défaut")
        reset.clicked.connect(self._reset_logo)
        ll.addWidget(reset)
        gl.addWidget(logo_grp)

        # ---- Section Tutoriel ----
        tut_grp = QGroupBox("Tutoriel")
        tutl = QVBoxLayout(tut_grp)
        relaunch = QPushButton("  Relancer le tutoriel")
        relaunch.setIcon(IconRenderer.icon('book', 18, get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)['text_primary']))
        relaunch.clicked.connect(self._relaunch_tutorial)
        tutl.addWidget(relaunch)
        tut_info = QLabel("Affiche le tutoriel pas à pas qui explique comment ajouter un jeu.")
        tut_info.setWordWrap(True)
        tut_info.setStyleSheet(f"color:{t['text_secondary']}; font-size:9px;")
        tutl.addWidget(tut_info)
        gl.addWidget(tut_grp)

        dlc_grp = QGroupBox("Options DLC")
        dl = QVBoxLayout(dlc_grp)
        self.auto_add_all_dlc_check = QCheckBox("Ajouter automatiquement tous les DLC d'un jeu")
        self.auto_add_all_dlc_check.setChecked(self.config.get('auto_add_all_dlc', False))
        dl.addWidget(self.auto_add_all_dlc_check)
        add_dlc = QPushButton("Ajouter tous les DLC des jeux existants")
        add_dlc.clicked.connect(self._add_dlc_existing)
        dl.addWidget(add_dlc)
        gl.addWidget(dlc_grp)

        discord_grp = QGroupBox("Présence Discord")
        ddl = QVBoxLayout(discord_grp)
        self.discord_check = QCheckBox("Activer la présence Discord")
        self.discord_check.setChecked(self.config.get('enable_discord_rpc', False))
        if not PPRESENCE_AVAILABLE:
            self.discord_check.setEnabled(False)
            self.discord_check.setText("Activer la présence Discord (pypresence non installé)")
        ddl.addWidget(self.discord_check)
        gl.addWidget(discord_grp)

        startup_grp = QGroupBox("Démarrage")
        stl = QVBoxLayout(startup_grp)
        self.startup_check = QCheckBox("Lancer Furry Tools au démarrage de Windows")
        self.startup_check.setChecked(is_in_startup())
        stl.addWidget(self.startup_check)
        gl.addWidget(startup_grp)

        auto_steam_grp = QGroupBox("Lancement automatique de Steam")
        asl = QVBoxLayout(auto_steam_grp)
        self.auto_steam_check = QCheckBox("Lancer Steam au démarrage de Furry Tools")
        self.auto_steam_check.setChecked(self.config.get('auto_launch_steam', False))
        asl.addWidget(self.auto_steam_check)
        gl.addWidget(auto_steam_grp)
        gl.addStretch()

        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setWidget(general)
        tabs.addTab(general_scroll, "Général")

        # ---------- Onglet Affichage ----------
        games = QWidget()
        gml = QVBoxLayout(games)
        grid_grp = QGroupBox("Configuration de la grille")
        ggl = QGridLayout(grid_grp)
        ggl.addWidget(QLabel("Colonnes :"), 0, 0)
        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(1, 4)
        self.grid_cols_spin.setValue(self.config.get('grid_columns', 2))
        ggl.addWidget(self.grid_cols_spin, 0, 1)
        ggl.addWidget(QLabel("Largeur grille (px) :"), 1, 0)
        self.grid_width_spin = QSpinBox()
        self.grid_width_spin.setRange(300, 800)
        self.grid_width_spin.setValue(self.config.get('grid_width', 400))
        ggl.addWidget(self.grid_width_spin, 1, 1)
        ggl.addWidget(QLabel("Hauteur max (px) :"), 2, 0)
        self.grid_height_spin = QSpinBox()
        self.grid_height_spin.setRange(300, 800)
        self.grid_height_spin.setValue(self.config.get('grid_max_height', 500))
        ggl.addWidget(self.grid_height_spin, 2, 1)
        gml.addWidget(grid_grp)

        btn_grp = QGroupBox("Configuration des boutons")
        bgl = QGridLayout(btn_grp)
        bgl.addWidget(QLabel("Largeur min (px) :"), 0, 0)
        self.btn_min_spin = QSpinBox()
        self.btn_min_spin.setRange(120, 300)
        self.btn_min_spin.setValue(self.config.get('button_min_width', 180))
        bgl.addWidget(self.btn_min_spin, 0, 1)
        bgl.addWidget(QLabel("Largeur max (px) :"), 1, 0)
        self.btn_max_spin = QSpinBox()
        self.btn_max_spin.setRange(150, 400)
        self.btn_max_spin.setValue(self.config.get('button_max_width', 250))
        bgl.addWidget(self.btn_max_spin, 1, 1)
        bgl.addWidget(QLabel("Hauteur (px) :"), 2, 0)
        self.btn_height_spin = QSpinBox()
        self.btn_height_spin.setRange(30, 80)
        self.btn_height_spin.setValue(self.config.get('button_height', 40))
        bgl.addWidget(self.btn_height_spin, 2, 1)
        bgl.addWidget(QLabel("Longueur max des noms :"), 3, 0)
        self.name_len_spin = QSpinBox()
        self.name_len_spin.setRange(20, 60)
        self.name_len_spin.setValue(self.config.get('name_max_length', 40))
        bgl.addWidget(self.name_len_spin, 3, 1)
        gml.addWidget(btn_grp)
        gml.addStretch()
        tabs.addTab(games, "Affichage des jeux")

        # ---------- Onglet Fenêtre ----------
        window = QWidget()
        wl = QVBoxLayout(window)
        win_grp = QGroupBox("Taille de la fenêtre des paramètres")
        wgl = QGridLayout(win_grp)
        wgl.addWidget(QLabel("Largeur (px) :"), 0, 0)
        self.dialog_width_spin = QSpinBox()
        self.dialog_width_spin.setRange(400, 1000)
        self.dialog_width_spin.setValue(self.config.get('dialog_width', 600))
        wgl.addWidget(self.dialog_width_spin, 0, 1)
        wgl.addWidget(QLabel("Hauteur (px) :"), 1, 0)
        self.dialog_height_spin = QSpinBox()
        self.dialog_height_spin.setRange(400, 900)
        self.dialog_height_spin.setValue(self.config.get('dialog_height', 600))
        wgl.addWidget(self.dialog_height_spin, 1, 1)
        wl.addWidget(win_grp)
        wl.addStretch()
        tabs.addTab(window, "Fenêtre")

        # ---------- Onglet Jeux privés ----------
        private = QWidget()
        pl = QVBoxLayout(private)
        priv_grp = QGroupBox("Jeux privés")
        pgl = QVBoxLayout(priv_grp)
        self.games_list = QListWidget()
        self.games_list.setSelectionMode(QListWidget.NoSelection)
        self.list_items = {}
        for appid in sorted(self.all_appids):
            item = QListWidgetItem(self.known_names.get(appid, appid))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if appid in self.config['private_games'] else Qt.Unchecked)
            item.setData(Qt.UserRole, appid)
            self.games_list.addItem(item)
            self.list_items[appid] = item
        pgl.addWidget(self.games_list)
        pl.addWidget(priv_grp)
        tabs.addTab(private, "Jeux privés")

        # ---------- Onglet Mise à jour ----------
        update = QWidget()
        ul = QVBoxLayout(update)
        ver_grp = QGroupBox("Version actuelle")
        vl = QHBoxLayout(ver_grp)
        vlabel = QLabel(f"Furry Tools V{CURRENT_VERSION}")
        vlabel.setStyleSheet("font-size:14px; font-weight:bold; color:#00cc66;")
        vl.addWidget(vlabel)
        ul.addWidget(ver_grp)
        check_grp = QGroupBox("Vérification des mises à jour")
        cl = QVBoxLayout(check_grp)
        self.auto_update_check = QCheckBox("Vérifier automatiquement au démarrage")
        self.auto_update_check.setChecked(self.config.get('auto_check_updates', True))
        cl.addWidget(self.auto_update_check)
        check_now = QPushButton("Vérifier maintenant")
        check_now.clicked.connect(self._check_updates)
        cl.addWidget(check_now)
        self.update_status_label = QLabel("")
        self.update_status_label.setWordWrap(True)
        cl.addWidget(self.update_status_label)
        ul.addWidget(check_grp)
        dl_grp = QGroupBox("Mise à jour")
        dgl = QVBoxLayout(dl_grp)
        self.download_btn = QPushButton("Télécharger la mise à jour")
        self.download_btn.clicked.connect(self._download_update)
        self.download_btn.setEnabled(False)
        dgl.addWidget(self.download_btn)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        dgl.addWidget(self.progress_bar)
        github = QPushButton("Ouvrir la page GitHub")
        github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        dgl.addWidget(github)
        ul.addWidget(dl_grp)
        ul.addStretch()
        tabs.addTab(update, "Mise à jour")

        main.addWidget(tabs)

        btns = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        main.addLayout(btns)

        if self.config.get('auto_check_updates', True):
            QTimer.singleShot(500, self._check_updates)

    # ---- Tutoriel ----
    def _relaunch_tutorial(self):
        if self.parent_window and hasattr(self.parent_window, 'show_tutorial'):
            self.accept()
            QTimer.singleShot(250, self.parent_window.show_tutorial)

    # ---- Police / logo ----
    def _update_preview(self):
        self.preview_text.setFont(QFont(self.font_family_combo.currentText(),
                                        self.font_size_slider.value()))

    def _update_logo_display(self):
        path = self.config.get('logo_path')
        if path and os.path.exists(path):
            self.logo_label.setText(f"Logo actuel : {os.path.basename(path)}")
        else:
            self.logo_label.setText("Logo actuel : par défaut")

    def _change_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir un logo", os.path.expanduser("~"),
                                              "Images (*.png *.jpg *.jpeg *.gif *.bmp *.ico)")
        if not path:
            return
        try:
            dest = os.path.join(CONFIG_DIR, "custom_logo" + os.path.splitext(path)[1].lower())
            shutil.copy2(path, dest)
            self.config['logo_path'] = dest
            self._update_logo_display()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la copie : {e}")

    def _reset_logo(self):
        self.config['logo_path'] = ''
        self._update_logo_display()

    # ---- Noms ----
    def _fetch_missing(self):
        missing = [a for a in self.all_appids if a not in self.known_names]
        if missing:
            self.name_fetcher = NameFetcher(missing)
            self.name_fetcher.names_ready.connect(self._update_names)
            self.name_fetcher.start()

    def _update_names(self, new_names):
        self.known_names.update(new_names)
        for appid, name in new_names.items():
            if appid in self.list_items:
                self.list_items[appid].setText(name)

    # ---- DLC ----
    def _add_dlc_existing(self):
        pw = self.parent_window
        if not pw or not getattr(pw, 'target_folder', None) or not os.path.exists(pw.target_folder):
            QMessageBox.warning(self, "Erreur", "Le dossier SteamTools n'existe pas.")
            return
        files = [f for f in os.listdir(pw.target_folder)
                 if f.lower().endswith('.lua') and f.lower() != 'steamtools.lua']
        if not files:
            QMessageBox.information(self, "Info", "Aucun fichier .lua trouvé.")
            return
        appids = [os.path.splitext(f)[0] for f in files]
        pd = QProgressDialog("", "Annuler", 0, len(appids), self)
        pd.setWindowTitle("Analyse des jeux")
        pd.setWindowModality(Qt.WindowModal)
        pd.setMinimumWidth(450)
        pd.setMinimumDuration(0)
        pd.setValue(0)
        steamtools_file = os.path.join(pw.target_folder, "Steamtools.lua")
        existing = []
        if os.path.exists(steamtools_file):
            with open(steamtools_file, 'r', encoding='utf-8') as f:
                for line in f:
                    m = re.search(r'addappid\((\d+),', line)
                    if m:
                        existing.append(m.group(1))
        status = {}
        for i, appid in enumerate(appids):
            if pd.wasCanceled():
                pd.close()
                return
            pd.setValue(i + 1)
            pd.setLabelText(f"Analyse {appid}...")
            QApplication.processEvents()
            try:
                url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
                with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10) as r:
                    data = json.loads(r.read().decode())
                if data.get(appid, {}).get('success'):
                    gd = data[appid]['data']
                    name = gd.get('name', appid)
                    self.game_names[appid] = name
                    if gd.get('dlc'):
                        missing = [str(d) for d in gd['dlc'] if str(d) not in existing]
                        if missing:
                            status[appid] = (name, len(missing))
            except Exception:
                pass
        pd.close()
        status = dict(sorted(status.items(), key=lambda x: x[1][0]))
        if not status:
            QMessageBox.information(self, "Info", "Tous les jeux ont déjà tous leurs DLC.")
            return
        dialog = SelectGameForDLCDialog(self, self.config, pw.target_folder, status,
                                        self.game_names, self._custom_themes)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_games:
            self._process_dlc(dialog.selected_games)

    def _process_dlc(self, game_appids):
        self._idx = 0
        self._added = self._skipped = self._failed = 0
        self._threads = []
        self._pd = QProgressDialog("", "Annuler", 0, len(game_appids), self)
        self._pd.setWindowTitle("Ajout des DLC")
        self._pd.setWindowModality(Qt.WindowModal)
        self._pd.setMinimumWidth(450)
        self._pd.setMinimumDuration(0)
        self._next_dlc(game_appids)

    def _next_dlc(self, game_appids):
        if self._pd.wasCanceled() or self._idx >= len(game_appids):
            self._pd.close()
            if self._pd.wasCanceled():
                return
            msg = f"Terminé !\n\nDLC ajoutés : {self._added}\n"
            if self._skipped:
                msg += f"DLC déjà présents : {self._skipped}\n"
            if self._failed:
                msg += f"DLC en échec : {self._failed}"
            QMessageBox.information(self, "Succès", msg)
            return
        appid = game_appids[self._idx]
        name = self.game_names.get(appid, appid)
        self._pd.setLabelText(f"Ajout des DLC pour {name}...")
        self._pd.setValue(self._idx + 1)
        QApplication.processEvents()
        thread = GameDLCDownloadThread(appid, self.parent_window.target_folder)
        thread.finished.connect(lambda a, s, f: self._dlc_done(a, s, f, game_appids))
        thread.error.connect(lambda e: self._dlc_done([], [], [], game_appids))
        self._threads.append(thread)
        thread.start()

    def _dlc_done(self, added, skipped, failed, game_appids):
        self._added += len(added)
        self._skipped += len(skipped)
        self._failed += len(failed)
        self._idx += 1
        self._next_dlc(game_appids)

    # ---- Mises à jour ----
    def _check_updates(self):
        self.update_status_label.setText("Vérification en cours...")
        self.download_btn.setEnabled(False)
        self.update_checker = UpdateChecker(CURRENT_VERSION)
        self.update_checker.update_checked.connect(self._on_update_checked)
        self.update_checker.start()

    def _on_update_checked(self, has_update, latest, current):
        if not latest:
            # latest vide => la vérification a échoué (réseau, GitHub indisponible...)
            self.update_status_label.setText(
                "Impossible de vérifier les mises à jour (vérifiez votre connexion).")
            self.download_btn.setEnabled(False)
        elif has_update:
            self.update_status_label.setText(f"Nouvelle version V{latest} disponible !")
            self.download_btn.setEnabled(True)
            self.latest_version = latest
        else:
            self.update_status_label.setText(f"Vous utilisez la dernière version V{current}")
            self.download_btn.setEnabled(False)

    def _download_update(self):
        save_path = os.path.join(tempfile.gettempdir(), "FurryTools_Update.zip")
        self.progress_bar.setVisible(True)
        # L'archive GitHub n'envoie pas toujours sa taille : barre indéterminée.
        self.progress_bar.setRange(0, 0)
        self.download_btn.setEnabled(False)
        self.update_status_label.setText("Téléchargement de la mise à jour...")
        self.update_downloader = UpdateDownloader(UPDATE_ZIP_URL, save_path)
        self.update_downloader.progress.connect(self._on_download_progress)
        self.update_downloader.finished.connect(self._on_download_done)
        self.update_downloader.error.connect(self._download_err)
        self.update_downloader.start()

    def _on_download_progress(self, value):
        # Si la taille est connue, on repasse en barre déterminée.
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def _on_download_done(self, path):
        # Version "frozen" (exe) : on ne peut pas remplacer les .py en cours d'exécution.
        if getattr(sys, 'frozen', False):
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)
            QMessageBox.information(
                self, "Mise à jour téléchargée",
                f"Téléchargée dans :\n{path}\n\nRemplacez les fichiers manuellement.")
            return
        self.update_status_label.setText("Installation de la mise à jour...")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.update_installer = UpdateInstaller(path, APP_DIR)
        self.update_installer.progress.connect(self.progress_bar.setValue)
        self.update_installer.finished.connect(self._on_install_done)
        self.update_installer.error.connect(self._download_err)
        self.update_installer.start()

    def _on_install_done(self, msg):
        self.progress_bar.setVisible(False)
        self.update_status_label.setText("Mise à jour installée.")
        if QMessageBox.question(
                self, "Mise à jour installée",
                f"{msg}.\n\nRedémarrer Furry Tools maintenant pour appliquer la mise à jour ?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._restart_app()

    def _restart_app(self):
        import subprocess
        from utils import release_instance_mutex
        main_py = os.path.join(APP_DIR, 'main.py')
        try:
            # Libérer le mutex AVANT de relancer, sinon la nouvelle instance
            # croit qu'une autre est déjà en cours et s'arrête aussitôt.
            release_instance_mutex()
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], cwd=APP_DIR)
            else:
                subprocess.Popen([sys.executable, main_py], cwd=APP_DIR)
        except Exception as e:
            QMessageBox.warning(self, "Redémarrage",
                                f"Redémarrage automatique impossible : {e}\n"
                                "Relancez l'application manuellement.")
            return
        QApplication.quit()

    def _download_err(self, msg):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        if QMessageBox.question(self, "Erreur",
                                f"Erreur : {msg}\n\nOuvrir GitHub pour télécharger manuellement ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(REPO_URL))
        self.download_btn.setEnabled(True)

    def closeEvent(self, event):
        # Stopper tous les threads en arrière-plan pour éviter les crashs
        # sur des widgets déjà détruits
        for attr in ('name_fetcher', 'update_checker', 'update_downloader', 'update_installer'):
            th = getattr(self, attr, None)
            if th and hasattr(th, 'isRunning') and th.isRunning():
                th.quit()
                th.wait(500)
        for th in getattr(self, '_threads', []):
            if th and th.isRunning():
                if hasattr(th, 'cancel'):
                    th.cancel()
                th.quit()
                th.wait(500)
        super().closeEvent(event)

    # ---- Sortie ----
    def get_updated_config(self):
        c = self.config
        c['icon_size'] = self.size_slider.value()
        c['enable_discord_rpc'] = self.discord_check.isChecked()
        c['start_with_windows'] = self.startup_check.isChecked()
        c['auto_launch_steam'] = self.auto_steam_check.isChecked()
        c['auto_check_updates'] = self.auto_update_check.isChecked()
        c['auto_add_all_dlc'] = self.auto_add_all_dlc_check.isChecked()
        c['font_family'] = self.font_family_combo.currentText()
        c['font_size'] = self.font_size_slider.value()
        c['grid_columns'] = self.grid_cols_spin.value()
        c['grid_width'] = self.grid_width_spin.value()
        c['grid_max_height'] = self.grid_height_spin.value()
        c['button_min_width'] = self.btn_min_spin.value()
        c['button_max_width'] = self.btn_max_spin.value()
        c['button_height'] = self.btn_height_spin.value()
        c['name_max_length'] = self.name_len_spin.value()
        c['dialog_width'] = self.dialog_width_spin.value()
        c['dialog_height'] = self.dialog_height_spin.value()
        c['private_games'] = [self.games_list.item(i).data(Qt.UserRole)
                              for i in range(self.games_list.count())
                              if self.games_list.item(i).checkState() == Qt.Checked]
        return c


# =============================================================================
# Éditeur de thème
# =============================================================================
class ThemeEditorDialog(QDialog):
    """Éditeur visuel pour créer ou modifier un thème personnalisé."""

    COLOR_KEYS = [
        ('bg_primary',     'Fond principal'),
        ('bg_secondary',   'Fond secondaire'),
        ('bg_tertiary',    'Fond tertiaire'),
        ('text_primary',   'Texte principal'),
        ('text_secondary', 'Texte secondaire'),
        ('border',         'Bordures'),
        ('border_focus',   'Bordures actives'),
        ('accent',         'Accent'),
        ('accent_hover',   'Accent (survol)'),
    ]

    def __init__(self, parent, config, custom_themes=None):
        super().__init__(parent)
        self.config = config
        self.custom_themes = custom_themes or {}
        t_name = config.get('theme', 'Violet profond')
        self.colors = dict(get_theme(t_name, self.custom_themes))
        self.setStyleSheet(get_theme_stylesheet(t_name, self.custom_themes))
        self.setWindowTitle("Éditeur de thème")
        self.setModal(True)
        w, h = get_scaled_size(820, 580)
        self.resize(w, h)
        self._color_btns = {}
        self._build()
        center_window(self)

    def _build(self):
        t = get_theme(self.config.get('theme', 'Violet profond'), self.custom_themes)
        main = QVBoxLayout(self)
        main.setSpacing(12)
        main.setContentsMargins(15, 15, 15, 15)

        # ── Nom + base ──────────────────────────────────────────────────
        name_grp = QGroupBox("Nouveau thème")
        name_lay = QHBoxLayout(name_grp)
        name_lay.addWidget(QLabel("Nom :"))
        self.name_edit = QLineEdit("Mon thème")
        self.name_edit.setPlaceholderText("Nom du thème...")
        name_lay.addWidget(self.name_edit, stretch=2)
        name_lay.addSpacing(20)
        name_lay.addWidget(QLabel("Partir de :"))
        self.base_combo = QComboBox()
        self.base_combo.addItems(list(get_all_themes(self.custom_themes).keys()))
        idx = self.base_combo.findText(self.config.get('theme', 'Violet profond'))
        if idx >= 0:
            self.base_combo.setCurrentIndex(idx)
        self.base_combo.currentTextChanged.connect(self._load_base)
        name_lay.addWidget(self.base_combo, stretch=1)
        main.addWidget(name_grp)

        # ── Contenu ──────────────────────────────────────────────────────
        content = QHBoxLayout()
        content.setSpacing(15)

        # Gauche : sélecteurs de couleurs
        left_grp = QGroupBox("Couleurs du thème")
        left_lay = QGridLayout(left_grp)
        left_lay.setSpacing(8)
        left_lay.setContentsMargins(12, 18, 12, 12)
        for row_i, (key, label) in enumerate(self.COLOR_KEYS):
            lbl = QLabel(label)
            btn = QPushButton()
            btn.setFixedSize(36, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Cliquer pour choisir : {label}")
            btn.clicked.connect(lambda _, k=key: self._pick(k))
            hex_lbl = QLabel(self.colors.get(key, '#000000'))
            hex_lbl.setStyleSheet(
                f"color:{t['text_secondary']}; font-size:10px; font-family:Consolas;")
            hex_lbl.setFixedWidth(72)
            self._color_btns[key] = (btn, hex_lbl)
            left_lay.addWidget(lbl, row_i, 0)
            left_lay.addWidget(btn, row_i, 1)
            left_lay.addWidget(hex_lbl, row_i, 2)
        content.addWidget(left_grp)

        # Droite : aperçu
        right_grp = QGroupBox("Aperçu en direct")
        right_lay = QVBoxLayout(right_grp)
        right_lay.setContentsMargins(12, 20, 12, 12)
        right_lay.setSpacing(0)

        self.preview_container = QWidget()
        pv_lay = QVBoxLayout(self.preview_container)
        pv_lay.setContentsMargins(12, 12, 12, 12)
        pv_lay.setSpacing(8)

        self._pv_title    = QLabel("Titre principal")
        self._pv_subtitle = QLabel("Texte secondaire — indication, aide")
        self._pv_btn      = QPushButton("Bouton exemple")
        self._pv_chk      = QCheckBox("Case à cocher")
        self._pv_edit     = QLineEdit()
        self._pv_edit.setPlaceholderText("Champ de saisie...")
        self._pv_list     = QListWidget()
        for i in range(3):
            self._pv_list.addItem(f"Élément de liste {i + 1}")
        self._pv_list.setMaximumHeight(84)
        self._pv_list.setSelectionMode(QListWidget.NoSelection)

        pv_lay.addWidget(self._pv_title)
        pv_lay.addWidget(self._pv_subtitle)
        pv_lay.addWidget(self._pv_btn)
        pv_lay.addWidget(self._pv_chk)
        pv_lay.addWidget(self._pv_edit)
        pv_lay.addWidget(self._pv_list)
        pv_lay.addStretch()

        right_lay.addWidget(self.preview_container)
        content.addWidget(right_grp)

        main.addLayout(content, stretch=1)

        # ── Boutons bas ───────────────────────────────────────────────────
        btns = QHBoxLayout()
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Enregistrer le thème")
        save.clicked.connect(self._save)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        main.addLayout(btns)

        self._refresh()

    def _load_base(self, name):
        self.colors = dict(get_theme(name, self.custom_themes))
        self._refresh()

    def _pick(self, key):
        color = QColorDialog.getColor(
            QColor(self.colors.get(key, '#000000')), self,
            f"Choisir la couleur : {key}")
        if color.isValid():
            self.colors[key] = color.name()
            self._refresh()

    def _refresh(self):
        c = self.colors
        t = get_theme(self.config.get('theme', 'Violet profond'), self.custom_themes)
        for key, (btn, hex_lbl) in self._color_btns.items():
            val = c.get(key, '#000000')
            btn.setStyleSheet(
                f"background-color:{val}; border:1px solid {t['border']}; border-radius:3px;")
            hex_lbl.setText(val)

        self.preview_container.setStyleSheet(
            f"background-color:{c['bg_primary']}; border-radius:6px;")
        self._pv_title.setStyleSheet(
            f"color:{c['text_primary']}; font-size:13px; font-weight:bold; background:transparent;")
        self._pv_subtitle.setStyleSheet(
            f"color:{c['text_secondary']}; font-size:10px; font-style:italic; background:transparent;")
        self._pv_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{c['bg_secondary']}; color:{c['text_primary']};
                border:1px solid {c['border']}; border-radius:4px; padding:6px 12px;
            }}
            QPushButton:hover {{ background-color:{c['accent_hover']}; }}
        """)
        self._pv_chk.setStyleSheet(f"""
            QCheckBox {{ color:{c['text_primary']}; spacing:8px; }}
            QCheckBox::indicator {{
                width:15px; height:15px;
                border:2px solid {c['border']}; border-radius:3px;
                background:{c['bg_secondary']};
            }}
            QCheckBox::indicator:checked {{
                background:{c['accent']}; border-color:{c['border_focus']};
            }}
        """)
        self._pv_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{c['bg_secondary']}; color:{c['text_primary']};
                border:1px solid {c['border']}; border-radius:4px; padding:4px 6px;
            }}
        """)
        self._pv_list.setStyleSheet(f"""
            QListWidget {{
                background:{c['bg_secondary']}; color:{c['text_primary']};
                border:1px solid {c['border']}; border-radius:4px; padding:2px;
            }}
            QListWidget::item {{ padding:4px 6px; }}
            QListWidget::item:hover {{ background:{c['accent_hover']}; }}
        """)

    def _save(self):
        import re as _re
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Nom requis", "Entrez un nom pour le thème.")
            return
        from themes_loader import THEMES_DIR
        safe = _re.sub(r'[^\w\-_. ]', '_', name).replace(' ', '_')
        path = os.path.join(THEMES_DIR, safe + '.json')
        data = {'name': name}
        data.update({k: self.colors.get(k, '#000000') for k, _ in self.COLOR_KEYS})
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(
                self, "Thème enregistré",
                f"Thème « {name} » enregistré !\n\n"
                f"Clic droit > Themes > Recharger les themes pour l'appliquer.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'enregistrer : {e}")


# =============================================================================
# Gestionnaire de thèmes (appliquer / supprimer / exporter / partager)
# =============================================================================
class _ThemeDragList(QListWidget):
    """Liste qui permet de glisser un thème personnalisé hors de la fenêtre
    (vers Discord, le bureau...) sous forme de fichier .json à partager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self._file_map = {}

    def set_file_map(self, mapping):
        self._file_map = mapping or {}

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        path = self._file_map.get(name)
        if not path or not os.path.exists(path):
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)


class ThemeManagerDialog(QDialog):
    """Gérer tous les thèmes : appliquer, supprimer (perso), exporter / partager."""

    def __init__(self, parent, config, custom_themes=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = config
        self._custom_themes = custom_themes or {}
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setWindowTitle("Gestionnaire de thèmes")
        self.setModal(True)
        w, h = get_scaled_size(560, 560)
        self.resize(w, h)
        self._build()
        center_window(self)

    def _build(self):
        from themes_loader import theme_file_map
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        self._file_map = theme_file_map()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        info = QLabel(
            "Double-cliquez pour appliquer un thème.\n"
            "Glissez un thème personnalisé hors de la fenêtre pour le partager "
            "(Discord, bureau...).")
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{t['text_secondary']}; font-size:10px;")
        layout.addWidget(info)

        self.theme_list = _ThemeDragList()
        self.theme_list.setStyleSheet(_list_style(t))
        self.theme_list.set_file_map(self._file_map)
        self.theme_list.itemSelectionChanged.connect(self._update_buttons)
        self.theme_list.itemDoubleClicked.connect(lambda _: self._apply())
        layout.addWidget(self.theme_list)
        self._populate_list()

        btns = QHBoxLayout()
        self.apply_btn = QPushButton("Appliquer")
        self.apply_btn.clicked.connect(self._apply)
        self.export_btn = QPushButton("Exporter / Partager")
        self.export_btn.clicked.connect(self._export)
        self.delete_btn = QPushButton("Supprimer")
        self.delete_btn.clicked.connect(self._delete)
        btns.addWidget(self.apply_btn)
        btns.addWidget(self.export_btn)
        btns.addWidget(self.delete_btn)
        layout.addLayout(btns)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self._update_buttons()

    def _populate_list(self):
        self.theme_list.clear()
        current = self.config.get('theme', 'Violet profond')
        for name in THEMES:
            label = ("● " if name == current else "     ") + name + "   (intégré)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            item.setData(Qt.UserRole + 1, 'builtin')
            self.theme_list.addItem(item)
        for name in self._custom_themes:
            label = ("● " if name == current else "     ") + name + "   (perso)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            item.setData(Qt.UserRole + 1, 'custom')
            self.theme_list.addItem(item)

    def _update_buttons(self):
        item = self.theme_list.currentItem()
        is_custom = bool(item) and item.data(Qt.UserRole + 1) == 'custom'
        self.apply_btn.setEnabled(bool(item))
        self.delete_btn.setEnabled(is_custom)
        self.export_btn.setEnabled(is_custom)

    def _restyle(self):
        """Réapplique le thème courant à la fenêtre du gestionnaire."""
        name = self.config.get('theme', 'Violet profond')
        self.setStyleSheet(get_theme_stylesheet(name, self._custom_themes))
        t = get_theme(name, self._custom_themes)
        self.theme_list.setStyleSheet(_list_style(t))

    def _apply(self):
        item = self.theme_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        if self.parent_window and hasattr(self.parent_window, '_apply_theme'):
            self.parent_window._apply_theme(name)
        self.config['theme'] = name
        self._restyle()
        self._populate_list()
        self._update_buttons()

    def _export(self):
        item = self.theme_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        path = self._file_map.get(name)
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Fichier du thème introuvable.")
            return
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(downloads, exist_ok=True)
            dest = os.path.join(downloads, os.path.basename(path))
            shutil.copy2(path, dest)
            QMessageBox.information(
                self, "Thème exporté",
                f"Thème exporté dans :\n{dest}\n\n"
                "Astuce : vous pouvez aussi glisser le thème directement depuis "
                "la liste vers Discord ou le bureau pour le partager.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'export : {e}")

    def _delete(self):
        item = self.theme_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        if QMessageBox.question(
                self, "Confirmation",
                f"Supprimer le thème « {name} » ?\nCette action est définitive.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        from themes_loader import delete_custom_theme, load_custom_themes, theme_file_map

        # Si le thème à supprimer est celui actuellement appliqué, on bascule
        # d'abord sur un autre thème : on ne supprime jamais le thème « en cours
        # d'usage », puis on supprime le fichier voulu.
        if self.config.get('theme') == name:
            fallback = self._fallback_theme(name)
            self.config['theme'] = fallback
            if self.parent_window and hasattr(self.parent_window, '_apply_theme'):
                self.parent_window._apply_theme(fallback)
            self._restyle()

        ok, err = delete_custom_theme(name)
        if not ok:
            QMessageBox.critical(self, "Erreur", f"Impossible de supprimer : {err}")
            return

        self._custom_themes = load_custom_themes()
        self._file_map = theme_file_map()
        self.theme_list.set_file_map(self._file_map)
        self._restyle()
        self._populate_list()
        self._update_buttons()
        QMessageBox.information(self, "Supprimé", f"Thème « {name} » supprimé.")

    def _fallback_theme(self, exclude):
        """Choisit un thème de repli intégré, différent de `exclude`."""
        if exclude != 'Violet profond' and 'Violet profond' in THEMES:
            return 'Violet profond'
        for n in THEMES:
            if n != exclude:
                return n
        return 'Violet profond'


# =============================================================================
# Crédits
# =============================================================================
class CreditsDialog(QDialog):
    """Fenêtre de crédits stylisée, thémée, déplaçable."""

    def __init__(self, parent, config, custom_themes=None):
        super().__init__(parent)
        self.config  = config
        self._custom_themes = custom_themes or {}
        self.theme   = get_theme(config.get('theme', 'Violet profond'), self._custom_themes)
        self._drag   = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        # Pas de WA_TranslucentBackground : évite le bug de "stretch" visuel
        # lors du déplacement sur Windows (artefact DWM/composition).
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setModal(True)
        self.setFixedSize(420, 480)
        self._build()
        center_window(self)

    # ------------------------------------------------------------------
    def _build(self):
        t = self.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(f"""
            #card {{
                background-color: {t['bg_primary']};
                border: 2px solid {t['accent']};
                border-radius: 18px;
            }}
        """)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 20, 30, 24)
        lay.setSpacing(0)

        # ── Bouton fermer (haut droite) ─────────────────────────────────
        top_row = QHBoxLayout()
        top_row.addStretch()
        x_btn = QPushButton()
        x_btn.setIcon(IconRenderer.icon('close', 13, QColor(t['text_secondary'])))
        x_btn.setFixedSize(26, 26)
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:13px; }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; }}
        """)
        x_btn.clicked.connect(self.accept)
        top_row.addWidget(x_btn)
        lay.addLayout(top_row)

        # ── Logo ────────────────────────────────────────────────────────
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setFixedHeight(78)
        logo_lbl.setPixmap(self._get_logo(68))
        lay.addWidget(logo_lbl)
        lay.addSpacing(6)

        # ── Nom + version ───────────────────────────────────────────────
        name = QLabel("FurryTools")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet(f"color:{t['text_primary']}; font-size:24px; font-weight:bold;")
        lay.addWidget(name)

        ver = QLabel(f"Version {CURRENT_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet(f"color:{t['text_secondary']}; font-size:11px;")
        lay.addWidget(ver)
        lay.addSpacing(4)

        tag = QLabel("Gestionnaire de manifests SteamTools")
        tag.setAlignment(Qt.AlignCenter)
        tag.setStyleSheet(f"color:{t['text_secondary']}; font-size:10px; font-style:italic;")
        lay.addWidget(tag)
        lay.addSpacing(16)

        # ── Création ────────────────────────────────────────────────────
        self._sep(lay, t)
        self._section(lay, t, "CREATION")
        self._row(lay, t, "Développeur", "rvmillions")
        lay.addSpacing(12)

        # ── Liens ────────────────────────────────────────────────────────
        self._sep(lay, t)
        self._section(lay, t, "LIENS")
        links = QHBoxLayout()
        links.addStretch()
        disc_btn = self._link_btn("Discord", t)
        disc_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_INVITE)))
        gh_btn = self._link_btn("GitHub", t)
        gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        links.addWidget(disc_btn)
        links.addSpacing(10)
        links.addWidget(gh_btn)
        links.addStretch()
        lay.addLayout(links)
        lay.addSpacing(12)

        # ── Technologies ────────────────────────────────────────────────
        self._sep(lay, t)
        self._section(lay, t, "TECHNOLOGIES")
        chips = QHBoxLayout()
        chips.addStretch()
        for label in ("Python 3.10", "PyQt5 5.15", "pypresence"):
            chips.addWidget(self._chip(label, t))
            chips.addSpacing(6)
        chips.addStretch()
        lay.addLayout(chips)
        lay.addSpacing(16)

        # ── Bas de page ─────────────────────────────────────────────────
        self._sep(lay, t)
        lay.addSpacing(8)

        made = QLabel("Réalisé avec passion pour la communauté Steam francophone")
        made.setAlignment(Qt.AlignCenter)
        made.setWordWrap(True)
        made.setStyleSheet(f"color:{t['text_secondary']}; font-size:9px; font-style:italic;")
        lay.addWidget(made)
        lay.addSpacing(14)

        close_btn = QPushButton("Fermer")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{t['accent']}; color:{t['text_primary']};
                border:none; border-radius:8px; font-size:11px; font-weight:bold;
                padding:6px 32px;
            }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _get_logo(self, size):
        """Retourne le pixmap du logo (logo.png si présent, sinon patte)."""
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        for p in (os.path.join(base, "logo.png"),
                  os.path.join(os.getcwd(), "logo.png"),
                  os.path.join(CONFIG_DIR, "logo.png")):
            if os.path.exists(p):
                pix = QPixmap(p)
                if not pix.isNull():
                    return pix.scaled(size, size,
                                      Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return IconRenderer.render('paw', size, QColor(self.theme['accent']))

    def _sep(self, lay, t):
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color:{t['border']}; margin:0;")
        lay.addWidget(line)
        lay.addSpacing(8)

    def _section(self, lay, t, title):
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color:{t['accent']}; font-size:9px; font-weight:bold; letter-spacing:2px;")
        lay.addWidget(lbl)
        lay.addSpacing(6)

    def _row(self, lay, t, label, value):
        row = QHBoxLayout()
        l = QLabel(label)
        l.setStyleSheet(f"color:{t['text_secondary']}; font-size:11px;")
        v = QLabel(value)
        v.setStyleSheet(f"color:{t['text_primary']}; font-size:11px; font-weight:bold;")
        row.addWidget(l)
        row.addStretch()
        row.addWidget(v)
        lay.addLayout(row)
        lay.addSpacing(4)

    def _link_btn(self, label, t):
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(32)
        btn.setMinimumWidth(110)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{t['bg_secondary']}; color:{t['text_primary']};
                border:1px solid {t['border']}; border-radius:6px;
                font-size:11px; padding:4px 14px;
            }}
            QPushButton:hover {{
                background-color:{t['accent_hover']};
                border-color:{t['border_focus']};
            }}
        """)
        return btn

    def _chip(self, label, t):
        c = QLabel(label)
        c.setStyleSheet(f"""
            color:{t['text_secondary']};
            background-color:{t['bg_secondary']};
            border:1px solid {t['border']};
            border-radius:4px;
            padding:4px 12px;
            font-size:10px;
        """)
        return c

    # ── Drag ──────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # self.pos() est plus fiable que frameGeometry() pour une fenêtre
            # sans cadre : évite le décalage visuel pendant le déplacement.
            self._drag = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag is not None:
            self.move(event.globalPos() - self._drag)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag = None
