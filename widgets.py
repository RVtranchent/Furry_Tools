"""Widgets personnalisés de Furry Tools."""
from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtWidgets import (QMenu, QWidget, QGridLayout, QScrollArea, QPushButton,
                             QWidgetAction, QSizePolicy, QAction)
from PyQt5.QtGui import QFont

from themes import get_theme


class GameGridMenu(QMenu):
    def __init__(self, title, parent=None, config=None, custom_themes=None):
        super().__init__(title, parent)
        self.config = config or {}
        self._custom_themes = custom_themes or {}
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)

        self.setStyleSheet(f"""
            QMenu {{
                background-color:{t['bg_primary']}; border:2px solid {t['border']};
                border-radius:10px; padding:10px;
            }}
            QMenu::item {{ background:transparent; color:{t['text_primary']}; }}
            QMenu::item:selected {{ background-color:{t['bg_secondary']}; }}
        """)

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet(f"background-color:{t['bg_primary']};")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.grid_widget)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background-color:{t['bg_primary']}; }}
            QScrollBar:vertical {{ background-color:{t['bg_secondary']}; width:10px; border-radius:5px; }}
            QScrollBar::handle:vertical {{ background-color:{t['accent']}; border-radius:5px; min-height:20px; }}
            QScrollBar::handle:vertical:hover {{ background-color:{t['accent_hover']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border:none; background:none; }}
            QScrollBar:horizontal {{ height:0px; }}
        """)

        gw = self.config.get('grid_width', 400)
        self.scroll.setMinimumWidth(gw - 20)
        self.scroll.setMaximumWidth(gw)
        self.scroll.setMaximumHeight(self.config.get('grid_max_height', 500))

        action = QWidgetAction(self)
        action.setDefaultWidget(self.scroll)
        self.addAction(action)
        self.game_buttons = []

    def add_game(self, appid, display_name, parent_window, font_size=10, font_family='Segoe UI'):
        t = get_theme(self.config.get('theme', 'Violet profond'), self._custom_themes)
        max_len = self.config.get('name_max_length', 40)
        short = display_name if len(display_name) <= max_len else display_name[:max_len - 3] + "..."

        btn = QPushButton(short)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setToolTip(display_name)
        btn.setFont(QFont(font_family, font_size))
        btn.setMinimumWidth(self.config.get('button_min_width', 180))
        btn.setMaximumWidth(self.config.get('button_max_width', 250))
        btn.setMinimumHeight(self.config.get('button_height', 40))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{t['bg_secondary']}; color:{t['text_primary']};
                border:1px solid {t['border']}; border-radius:4px; padding:8px;
                text-align:left; font-size:{font_size}px; font-family:'{font_family}';
            }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; border:1px solid {t['border_focus']}; }}
            QPushButton:pressed {{ background-color:{t['accent']}; }}
        """)

        def show_game_menu():
            menu = QMenu(btn)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color:{t['bg_primary']}; color:{t['text_primary']};
                    border:2px solid {t['border']}; border-radius:6px; padding:5px;
                    font-size:{font_size}px; font-family:'{font_family}';
                }}
                QMenu::item {{ padding:6px 15px; border-radius:3px; color:{t['text_primary']}; }}
                QMenu::item:selected {{ background-color:{t['bg_secondary']}; }}
            """)
            delete_action = QAction("Supprimer", menu)
            delete_action.triggered.connect(lambda: parent_window.delete_game(appid))
            menu.addAction(delete_action)
            steamdb_action = QAction("SteamDB", menu)
            steamdb_action.triggered.connect(lambda: parent_window.open_steamdb(appid))
            menu.addAction(steamdb_action)
            if parent_window.config.get('auto_add_all_dlc', False):
                add_dlc_action = QAction("Ajouter tous les DLC", menu)
                add_dlc_action.triggered.connect(lambda: parent_window.add_all_dlc_for_game(appid))
                menu.addAction(add_dlc_action)
            menu.exec_(btn.mapToGlobal(QPoint(0, btn.height())))

        btn.clicked.connect(show_game_menu)
        self.game_buttons.append((appid, btn, display_name))

    def layout_games(self):
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        if not self.game_buttons:
            return
        cols = self.config.get('grid_columns', 2)
        row = col = 0
        for appid, btn, _ in self.game_buttons:
            self.grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1
