"""Gestionnaire de plugins FurryTools — guide de création + liste des plugins."""
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QFrame, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit, QScrollArea, QTabWidget,
)

from themes import get_theme
from icons import IconRenderer
from utils import center_window
from plugins_loader import PLUGINS_DIR


class PluginsDialog(QDialog):
    """Dialogue : onglet Guide (tutoriel + exemples) + onglet Plugins chargés."""

    def __init__(self, parent, config, plugins, custom_themes=None):
        super().__init__(parent)
        self.config  = config
        self._custom_themes = custom_themes or {}
        self.theme   = get_theme(config.get('theme', 'Violet profond'), self._custom_themes)
        self.plugins = plugins
        self._drag   = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        from themes import get_theme_stylesheet
        self.setStyleSheet(get_theme_stylesheet(config.get('theme', 'Violet profond'),
                                                self._custom_themes))
        self.setModal(True)
        self.setFixedSize(680, 580)
        self._build()
        center_window(self)

    # ──────────────────────────────────────────────────────────────────────────
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
                border-radius: 14px;
            }}
        """)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(0)

        # ── Barre de titre ─────────────────────────────────────────────
        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(IconRenderer.render('book', 20, QColor(t['accent'])))
        ico.setFixedSize(22, 22)
        hdr.addWidget(ico)
        hdr.addSpacing(8)
        title = QLabel("Gestionnaire de plugins")
        title.setStyleSheet(
            f"color:{t['text_primary']}; font-size:15px; font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        x = QPushButton()
        x.setIcon(IconRenderer.icon('close', 13, QColor(t['text_secondary'])))
        x.setFixedSize(26, 26)
        x.setCursor(Qt.PointingHandCursor)
        x.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:13px; }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; }}
        """)
        x.clicked.connect(self.accept)
        hdr.addWidget(x)
        lay.addLayout(hdr)
        lay.addSpacing(10)

        # ── Onglets ────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {t['border']};
                border-radius: 0 6px 6px 6px;
                background: {t['bg_primary']};
            }}
            QTabBar::tab {{
                background: {t['bg_secondary']};
                color: {t['text_secondary']};
                border: 1px solid {t['border']};
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                padding: 6px 20px;
                font-size: 11px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {t['accent']};
                color: {t['text_primary']};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background: {t['accent_hover']};
                color: {t['text_primary']};
            }}
        """)
        tabs.addTab(self._tab_guide(t), "Guide de création")
        tabs.addTab(self._tab_plugins(t), f"Plugins chargés  ({len(self.plugins)})")
        lay.addWidget(tabs, stretch=1)
        lay.addSpacing(10)

        # ── Pied de page ───────────────────────────────────────────────
        foot = QHBoxLayout()
        btn_folder = self._btn_secondary("Ouvrir le dossier plugins", t)
        btn_folder.clicked.connect(self._open_folder)
        btn_close = self._btn_primary("Fermer", t)
        btn_close.clicked.connect(self.accept)
        foot.addWidget(btn_folder)
        foot.addStretch()
        foot.addWidget(btn_close)
        lay.addLayout(foot)

    # ──────────────────────────────────────────────────────────────────────────
    # ONGLET GUIDE
    # ──────────────────────────────────────────────────────────────────────────
    def _tab_guide(self, t):
        outer = QWidget()
        outer.setStyleSheet(f"background:{t['bg_primary']};")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea  {{ border:none; background:{t['bg_primary']}; }}
            QScrollBar:vertical {{
                background:{t['bg_secondary']}; width:7px; border-radius:3px;
            }}
            QScrollBar::handle:vertical {{
                background:{t['border']}; border-radius:3px; min-height:20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)

        inner = QWidget()
        inner.setStyleSheet(f"background:{t['bg_primary']};")
        vlay = QVBoxLayout(inner)
        vlay.setContentsMargins(14, 14, 14, 14)
        vlay.setSpacing(4)

        # ── Intro ──────────────────────────────────────────────────────
        intro = QLabel(
            "Placez un fichier <b>.py</b> dans le dossier <b>plugins/</b> "
            "— il est chargé automatiquement au démarrage de FurryTools.")
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color:{t['text_secondary']}; font-size:11px; "
            f"background:{t['bg_secondary']}; border-radius:6px; padding:8px 12px;")
        vlay.addWidget(intro)
        vlay.addSpacing(10)

        # ── Sections ───────────────────────────────────────────────────
        SECTIONS = [
            (
                "1  —  Structure de base",
                "Un plugin minimal : métadonnées + fonction register().",
                """\
# ─── Métadonnées (facultatif mais recommandé) ───────────────
PLUGIN_NAME        = "Mon Plugin"
PLUGIN_VERSION     = "1.0.0"
PLUGIN_AUTHOR      = "Votre pseudo"
PLUGIN_DESCRIPTION = "Ce que fait ce plugin"

# ─── Fonction principale ─────────────────────────────────────
def register(app):
    \"\"\"
    Appelé au démarrage.  Retourne une liste de QAction.
    Ces actions s'affichent dans le menu  Plugins > Mon Plugin.
    \"\"\"
    from PyQt5.QtWidgets import QAction
    action = QAction("Dire bonjour")
    action.triggered.connect(dire_bonjour)
    return [action]

def dire_bonjour():
    from PyQt5.QtWidgets import QMessageBox
    QMessageBox.information(None, "Mon Plugin", "Bonjour !")"""
            ),
            (
                "2  —  Accéder aux données de FurryTools",
                "app donne accès à toute l'application.",
                """\
# ─── Attributs disponibles via app ──────────────────────────
#   app.config          dict  — Configuration utilisateur complète
#   app.steam_folder    str   — Dossier Steam (ex: C:/Program Files/Steam)
#   app.steam_path      str   — Chemin vers steam.exe
#   app.target_folder   str   — Dossier stplug-in (là où vont les manifests)
#   app.game_names      dict  — Cache { appid: "Nom du jeu" }

def register(app):
    from PyQt5.QtWidgets import QAction, QMessageBox
    action = QAction("Afficher les infos Steam")
    action.triggered.connect(lambda: QMessageBox.information(
        None, "Infos",
        "Steam     : " + str(app.steam_folder) + "\\n" +
        "Manifests : " + str(app.target_folder) + "\\n" +
        "Theme     : " + app.config.get("theme", "?") + "\\n" +
        "Jeux      : " + str(len(app.game_names)) + " en cache"
    ))
    return [action]"""
            ),
            (
                "3  —  Plusieurs actions dans le menu",
                "register() peut retourner plusieurs QAction.",
                """\
def register(app):
    from PyQt5.QtWidgets import QAction

    a1 = QAction("Action 1 — Infos Steam")
    a1.triggered.connect(lambda: action1(app))

    a2 = QAction("Action 2 — Copier chemin Steam")
    a2.triggered.connect(lambda: action2(app))

    a3 = QAction("Action 3 — Compter les manifests")
    a3.triggered.connect(lambda: action3(app))

    return [a1, a2, a3]      # les 3 actions apparaissent dans le menu

def action1(app): ...
def action2(app): ...
def action3(app): ..."""
            ),
            (
                "4  —  Ouvrir une fenêtre personnalisée",
                "Un plugin peut créer sa propre interface Qt.",
                """\
def register(app):
    from PyQt5.QtWidgets import QAction
    action = QAction("Ouvrir ma fenêtre")
    action.triggered.connect(lambda: ouvrir_fenetre(app))
    return [action]

def ouvrir_fenetre(app):
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout,
                                  QLabel, QPushButton)
    dlg = QDialog()
    dlg.setWindowTitle("Ma fenêtre plugin")
    dlg.resize(320, 160)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Steam : " + str(app.steam_folder)))
    lay.addWidget(QLabel("Jeux  : " + str(len(app.game_names))))
    btn = QPushButton("Fermer")
    btn.clicked.connect(dlg.accept)
    lay.addWidget(btn)
    dlg.exec_()"""
            ),
            (
                "5  —  Règles importantes",
                None,
                """\
# Les fichiers commençant par  _  sont IGNORÉS.
#   Exemple : _mon_plugin_pause.py  →  non chargé

# En cas d'erreur dans un plugin, il est ignoré et
# l'erreur est enregistrée dans les logs FurryTools.
# Les autres plugins continuent de fonctionner.

# Les plugins sont chargés par ordre alphabétique.

# Redémarrez FurryTools après avoir ajouté/modifié
# un fichier dans le dossier plugins/."""
            ),
        ]

        for title, intro_txt, code in SECTIONS:
            # Titre
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(
                f"color:{t['accent']}; font-size:12px; font-weight:bold;")
            vlay.addWidget(t_lbl)
            vlay.addSpacing(2)

            # Intro
            if intro_txt:
                i_lbl = QLabel(intro_txt)
                i_lbl.setWordWrap(True)
                i_lbl.setStyleSheet(
                    f"color:{t['text_secondary']}; font-size:10px;")
                vlay.addWidget(i_lbl)
                vlay.addSpacing(4)

            # Bloc de code
            box = QTextEdit()
            box.setReadOnly(True)
            box.setPlainText(code)
            box.setFont(QFont("Consolas", 9))
            lines = code.count('\n') + 1
            box.setFixedHeight(min(lines * 16 + 22, 260))
            box.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {t['bg_secondary']};
                    color: {t['text_primary']};
                    border: 1px solid {t['border']};
                    border-radius: 6px;
                    padding: 8px 10px;
                    selection-background-color: {t['accent']};
                }}
                QScrollBar:vertical {{
                    background:{t['bg_secondary']}; width:6px;
                }}
                QScrollBar::handle:vertical {{
                    background:{t['border']}; border-radius:3px;
                }}
            """)
            vlay.addWidget(box)
            vlay.addSpacing(14)

        vlay.addStretch()
        scroll.setWidget(inner)

        tab_lay = QVBoxLayout(outer)
        tab_lay.setContentsMargins(0, 0, 0, 0)
        tab_lay.addWidget(scroll)
        return outer

    # ──────────────────────────────────────────────────────────────────────────
    # ONGLET PLUGINS CHARGÉS
    # ──────────────────────────────────────────────────────────────────────────
    def _tab_plugins(self, t):
        outer = QWidget()
        outer.setStyleSheet(f"background:{t['bg_primary']};")
        vlay = QVBoxLayout(outer)
        vlay.setContentsMargins(14, 14, 14, 14)
        vlay.setSpacing(0)

        if not self.plugins:
            lbl = QLabel(
                "Aucun plugin chargé.\n\n"
                "Ajoutez des fichiers .py dans le dossier plugins/\n"
                "et redémarrez FurryTools.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color:{t['text_secondary']}; font-size:11px;")
            vlay.addStretch()
            vlay.addWidget(lbl)
            vlay.addStretch()
            return outer

        # ── En-tête tableau ────────────────────────────────────────────
        COLS = [("Nom", 165), ("Version", 65), ("Auteur", 110),
                ("Actions", 62), ("Description", 0)]
        hdr = QHBoxLayout()
        for col, w in COLS:
            lbl = QLabel(col)
            lbl.setStyleSheet(
                f"color:{t['accent']}; font-size:9px; font-weight:bold; "
                f"letter-spacing:1px; padding-bottom:2px;")
            if w:
                lbl.setFixedWidth(w)
            else:
                lbl.setSizePolicy(
                    lbl.sizePolicy().horizontalPolicy(),
                    lbl.sizePolicy().verticalPolicy())
            hdr.addWidget(lbl)
        hdr.addStretch()
        vlay.addLayout(hdr)

        sep0 = QLabel()
        sep0.setFixedHeight(1)
        sep0.setStyleSheet(f"background:{t['accent']}; margin-bottom:6px;")
        vlay.addWidget(sep0)
        vlay.addSpacing(6)

        # ── Lignes ─────────────────────────────────────────────────────
        for plugin in self.plugins:
            row = QHBoxLayout()
            row.setSpacing(0)

            name = QLabel(plugin['name'])
            name.setFixedWidth(165)
            name.setStyleSheet(
                f"color:{t['text_primary']}; font-size:11px; font-weight:bold;")

            ver = QLabel(plugin['version'])
            ver.setFixedWidth(65)
            ver.setStyleSheet(f"color:{t['text_secondary']}; font-size:10px;")

            auth = QLabel(plugin['author'])
            auth.setFixedWidth(110)
            auth.setStyleSheet(f"color:{t['text_secondary']}; font-size:10px;")

            n = len(plugin['actions'])
            badge = QLabel(str(n))
            badge.setFixedWidth(62)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"color:{'white' if n else t['text_secondary']};"
                f"background:{ t['accent'] if n else t['bg_secondary'] };"
                f"border-radius:4px; font-size:10px; font-weight:bold; padding:2px 0;")

            desc = QLabel(plugin['desc'] or "—")
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color:{t['text_secondary']}; font-size:10px; padding-left:4px;")

            row.addWidget(name)
            row.addWidget(ver)
            row.addWidget(auth)
            row.addWidget(badge)
            row.addWidget(desc, stretch=1)
            vlay.addLayout(row)
            vlay.addSpacing(4)

            line = QLabel()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background:{t['bg_secondary']};")
            vlay.addWidget(line)
            vlay.addSpacing(4)

        vlay.addStretch()
        return outer

    # ──────────────────────────────────────────────────────────────────────────
    def _btn_primary(self, txt, t):
        b = QPushButton(txt)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(32)
        b.setStyleSheet(f"""
            QPushButton {{
                background:{t['accent']}; color:{t['text_primary']};
                border:none; border-radius:6px;
                font-size:11px; font-weight:bold; padding:4px 24px;
            }}
            QPushButton:hover {{ background:{t['accent_hover']}; }}
        """)
        return b

    def _btn_secondary(self, txt, t):
        b = QPushButton(txt)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(32)
        b.setStyleSheet(f"""
            QPushButton {{
                background:{t['bg_secondary']}; color:{t['text_primary']};
                border:1px solid {t['border']}; border-radius:6px;
                font-size:11px; padding:4px 16px;
            }}
            QPushButton:hover {{
                background:{t['accent_hover']}; border-color:{t['border_focus']};
            }}
        """)
        return b

    def _open_folder(self):
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        try:
            os.startfile(PLUGINS_DIR)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag is not None:
            self.move(event.globalPos() - self._drag)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag = None
