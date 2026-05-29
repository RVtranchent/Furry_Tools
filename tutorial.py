"""Système de tutoriel animé de Furry Tools (réécrit, stable).

Corrections par rapport à la v1.0.9 :
 - Plus de QGraphicsDropShadowEffect (causait les erreurs QPainter / UpdateLayeredWindowIndirect)
 - Plus de QGraphicsOpacityEffect empilés : on utilise QStackedWidget (zéro chevauchement de texte)
 - Confettis dans une fenêtre top-level séparée (pas enfant d'un widget à effet)
 - Icônes vectorielles dessinées au QPainter (aucun emoji)
 - La fermeture du tutoriel ne quitte plus l'application
"""
from PyQt5.QtCore import (Qt, QPoint, QPointF, QUrl, QTimer, QRectF,
                          QPropertyAnimation, QEasingCurve, QAbstractAnimation,
                          pyqtProperty)
from PyQt5.QtGui import (QColor, QPainter, QBrush, QPen, QRadialGradient,
                         QDesktopServices, QFont)
from PyQt5.QtWidgets import (QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
                             QPushButton, QProgressBar, QCheckBox, QStackedWidget,
                             QApplication, QFrame, QSizePolicy)

from themes import get_theme
from icons import IconRenderer
from config import save_config, DISCORD_INVITE


# ----------------------------------------------------------------------
# Halo pulsant autour du logo principal
# ----------------------------------------------------------------------
class PulseHaloWidget(QWidget):
    def __init__(self, target_widget, color="#9a7cc0"):
        super().__init__(None)
        self.target = target_widget
        self.color = QColor(color)
        self._phase = 0.0
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._update_geometry()

        self.animation = QPropertyAnimation(self, b"phase", self)
        self.animation.setDuration(1400)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setLoopCount(-1)
        self.animation.start()

        self.tracker = QTimer(self)
        self.tracker.timeout.connect(self._update_geometry)
        self.tracker.start(60)

    def get_phase(self):
        return self._phase

    def set_phase(self, value):
        self._phase = value
        self.update()

    phase = pyqtProperty(float, get_phase, set_phase)

    def _update_geometry(self):
        if not self.target or not self.target.isVisible():
            return
        pad = 80
        rect = self.target.geometry()
        gp = self.target.mapToGlobal(QPoint(0, 0))
        self.setGeometry(gp.x() - pad, gp.y() - pad,
                         rect.width() + pad * 2, rect.height() + pad * 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        max_r = min(self.width(), self.height()) / 2
        r = max_r * self._phase
        if r <= 1:
            painter.end()
            return
        gradient = QRadialGradient(center, r)
        col = QColor(self.color)
        col.setAlphaF(max(0.0, (1.0 - self._phase) * 0.55))
        gradient.setColorAt(0.65, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, col)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, r, r)
        painter.end()

    def stop(self):
        try:
            self.animation.stop()
            self.tracker.stop()
            self.close()
            self.deleteLater()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Confettis (fenêtre top-level transparente => pas de conflit de painter)
# ----------------------------------------------------------------------
class ConfettiWindow(QWidget):
    def __init__(self, theme):
        super().__init__(None)
        import random
        self._random = random
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.particles = []
        self.colors = [QColor("#ff6b6b"), QColor("#4ecdc4"), QColor("#ffe66d"),
                       QColor("#a8e6cf"), QColor("#c08eff"), QColor("#ff9a9e"),
                       QColor(theme['accent']), QColor(theme['border_focus'])]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._spawns_left = 8

    def start(self):
        self._spawn(70)
        self.timer.start(16)

    def _spawn(self, count):
        r = self._random
        w = max(1, self.width())
        for _ in range(count):
            self.particles.append({
                'x': r.uniform(0, w), 'y': r.uniform(-40, 0),
                'vx': r.uniform(-2.2, 2.2), 'vy': r.uniform(2, 5),
                'size': r.uniform(6, 13), 'rot': r.uniform(0, 360),
                'vrot': r.uniform(-9, 9), 'color': r.choice(self.colors)
            })

    def _tick(self):
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.15
            p['rot'] += p['vrot']
        self.particles = [p for p in self.particles if p['y'] < self.height() + 40]
        if self._spawns_left > 0:
            self._spawns_left -= 1
            self._spawn(18)
        self.update()
        if not self.particles and self._spawns_left <= 0:
            self.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for p in self.particles:
            painter.save()
            painter.translate(p['x'], p['y'])
            painter.rotate(p['rot'])
            painter.setBrush(p['color'])
            painter.setPen(Qt.NoPen)
            s = p['size']
            painter.drawRoundedRect(QRectF(-s / 2, -s / 4, s, s / 2), 1.5, 1.5)
            painter.restore()
        painter.end()

    def stop(self):
        try:
            self.timer.stop()
            self.close()
            self.deleteLater()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Fenêtre principale du tutoriel
# ----------------------------------------------------------------------
class TutorialDialog(QDialog):

    STEPS = [
        {'icon': 'paw', 'title': "Bienvenue dans Furry Tools !",
         'desc': "Ce tutoriel va te guider pas à pas pour ajouter un jeu à ta "
                 "bibliothèque Steam grâce à Furry Tools.\n\n"
                 "Le processus se fait en 8 étapes simples. C'est parti !",
         'hint': "Tu peux relancer ce tutoriel à tout moment depuis le menu (clic droit)."},

        {'icon': 'mouse', 'title': "Étape 1 — Ouvrir la recherche",
         'desc': "Fais un clic droit sur le logo flottant de Furry Tools, puis "
                 "clique sur l'option « Rechercher un jeu Steam ».",
         'hint': "Le logo est la petite icône qui flotte sur ton bureau.",
         'halo': True},

        {'icon': 'keyboard', 'title': "Étape 2 — Chercher le jeu",
         'desc': "Dans la barre de recherche qui s'ouvre, tape le nom du jeu "
                 "que tu veux ajouter (ex : Hogwarts Legacy, Elden Ring...).\n\n"
                 "Les résultats apparaissent automatiquement.",
         'hint': "Tape au moins 3 caractères pour lancer la recherche."},

        {'icon': 'pointer', 'title': "Étape 3 — Sélectionner le jeu",
         'desc': "Dans la liste des résultats, double-clique sur le jeu qui "
                 "t'intéresse.\n\nUn menu va apparaître avec plusieurs options."},

        {'icon': 'clipboard', 'title': "Étape 4 — Copier la commande",
         'desc': "Dans le menu qui s'affiche, choisis « Copier la commande /gen ».\n\n"
                 "La commande est automatiquement copiée dans ton presse-papiers.",
         'hint': "La commande ressemble à : /gen appid:1234567"},

        {'icon': 'chat', 'title': "Étape 5 — Rejoindre Discord",
         'desc': "Va sur le serveur Discord Lightning Project.\n\n"
                 "Si tu n'y es pas encore, clique sur le bouton ci-dessous pour le rejoindre.",
         'action': {'label': "Ouvrir Discord", 'icon': 'chat', 'do': 'discord'}},

        {'icon': 'send', 'title': "Étape 6 — Envoyer la commande",
         'desc': "Sur Discord, rends-toi dans ce salon, puis colle ta commande "
                 "(Ctrl+V) et appuie sur Entrée.",
         'channel': 'manifest-generator',
         'hint': "Attends quelques secondes que le bot réponde."},

        {'icon': 'download', 'title': "Étape 7 — Télécharger le ZIP",
         'desc': "Le bot va t'envoyer un fichier ZIP contenant les manifests du jeu.\n\n"
                 "Clique dessus pour le télécharger sur ton ordinateur.",
         'hint': "Le fichier se trouve généralement dans ton dossier « Téléchargements »."},

        {'icon': 'target', 'title': "Étape 8 — Installer le jeu",
         'desc': "Dernière étape ! Glisse-dépose le fichier ZIP directement sur le "
                 "logo flottant de Furry Tools.\n\nL'application va automatiquement "
                 "extraire et installer les manifests dans Steam.",
         'hint': "Regarde le logo pulser — c'est ta cible !",
         'halo': True},

        {'icon': 'trophy', 'title': "Bravo, c'est terminé !",
         'desc': "Tu maîtrises maintenant le workflow complet de Furry Tools.\n\n"
                 "Redémarre Steam et profite de ton jeu !",
         'final': True},
    ]

    def __init__(self, parent, config, main_window=None, custom_themes=None):
        # parent = main_window pour que la fermeture n'affecte pas l'app
        super().__init__(parent)
        self.config = config
        self.main_window = main_window
        self._custom_themes = custom_themes or {}
        self.theme = get_theme(config.get('theme', 'Violet profond'), self._custom_themes)
        self.current = 0
        self.halo = None
        self.confetti = None
        self._drag_pos = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(False)
        self.setFixedSize(660, 580)

        self._build_ui()
        self._show_step(0)

    # ------------------------------------------------------------------
    def _build_ui(self):
        t = self.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        # Carte arrondie opaque (PAS d'ombre -> évite le crash QPainter)
        self.card = QFrame(self)
        self.card.setObjectName("card")
        self.card.setStyleSheet(f"""
            #card {{
                background-color: {t['bg_primary']};
                border: 2px solid {t['accent']};
                border-radius: 16px;
            }}
        """)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(14)

        # ---- Header ----
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(IconRenderer.render('paw', 26, QColor(t['accent'])))
        logo.setFixedSize(28, 28)
        header.addWidget(logo)
        title = QLabel("Tutoriel Furry Tools")
        title.setStyleSheet(f"color:{t['text_primary']}; font-size:16px; font-weight:bold;")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton()
        close_btn.setIcon(IconRenderer.icon('close', 16, QColor(t['text_secondary'])))
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:15px; }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; }}
        """)
        close_btn.clicked.connect(self._finish)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # ---- Progression ----
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet(f"color:{t['text_secondary']}; font-size:11px;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.STEPS) - 1)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color:{t['bg_secondary']}; border:none; border-radius:3px; }}
            QProgressBar::chunk {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {t['accent']}, stop:1 {t['border_focus']});
                border-radius:3px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # ---- Pages (QStackedWidget => aucun chevauchement) ----
        self.stack = QStackedWidget()
        for step in self.STEPS:
            self.stack.addWidget(self._make_page(step))
        layout.addWidget(self.stack, stretch=1)

        # ---- Footer ----
        self.dont_show = QCheckBox("Ne plus afficher ce tutoriel au démarrage")
        self.dont_show.setChecked(self.config.get('tutorial_shown', False))
        self.dont_show.setStyleSheet(f"""
            QCheckBox {{
                color:{t['text_secondary']}; font-size:11px; spacing:8px;
            }}
            QCheckBox::indicator {{
                width:17px; height:17px;
                border:2px solid {t['border']};
                border-radius:4px;
                background-color:transparent;
            }}
            QCheckBox::indicator:hover {{
                border-color:{t['accent']};
            }}
            QCheckBox::indicator:checked {{
                background-color:{t['accent']};
                border:2px solid {t['border_focus']};
                image:none;
            }}
            QCheckBox::indicator:checked:hover {{
                background-color:{t['accent_hover']};
            }}
        """)
        layout.addWidget(self.dont_show, alignment=Qt.AlignCenter)

        nav = QHBoxLayout()
        nav.setSpacing(10)
        self.prev_btn = QPushButton("Précédent")
        self.prev_btn.setIcon(IconRenderer.icon('arrow_left', 16, QColor(t['text_primary'])))
        self.skip_btn = QPushButton("Passer")
        self.next_btn = QPushButton("Suivant")
        self.next_btn.setIcon(IconRenderer.icon('arrow_right', 16, QColor(t['text_primary'])))
        self.next_btn.setLayoutDirection(Qt.RightToLeft)  # icône à droite du texte
        for b in (self.prev_btn, self.skip_btn, self.next_btn):
            b.setMinimumHeight(38)
            b.setMinimumWidth(130)
            b.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setStyleSheet(self._secondary_btn())
        self.skip_btn.setStyleSheet(self._secondary_btn())
        self.next_btn.setStyleSheet(self._primary_btn())
        self.prev_btn.clicked.connect(self._prev)
        self.skip_btn.clicked.connect(self._finish)
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.skip_btn)
        nav.addWidget(self.next_btn)
        layout.addLayout(nav)

    def _make_page(self, step):
        """Crée une page d'étape avec des hauteurs maîtrisées (pas d'overlap)."""
        t = self.theme
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignTop)

        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedHeight(96)
        icon.setPixmap(IconRenderer.render(step['icon'], 84, QColor(t['accent'])))
        lay.addWidget(icon)

        title = QLabel(step['title'])
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet(f"color:{t['text_primary']}; font-size:18px; font-weight:bold;")
        lay.addWidget(title)

        desc = QLabel(step['desc'])
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setMinimumHeight(96)
        desc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        desc.setStyleSheet(f"color:{t['text_secondary']}; font-size:12px; padding:0 18px;")
        lay.addWidget(desc)

        if step.get('channel'):
            ch_lbl = QLabel(f"# {step['channel']}")
            ch_lbl.setAlignment(Qt.AlignCenter)
            ch_lbl.setWordWrap(False)
            ch_lbl.setStyleSheet(f"""
                color: {t['border_focus']};
                background-color: {t['bg_secondary']};
                border: 2px solid {t['border']};
                border-radius: 8px;
                padding: 10px 28px;
                font-size: 15px;
                font-weight: bold;
                font-family: 'Consolas', 'Courier New', monospace;
            """)
            ch_lbl.setMinimumHeight(46)
            ch_wrap = QHBoxLayout()
            ch_wrap.addStretch()
            ch_wrap.addWidget(ch_lbl)
            ch_wrap.addStretch()
            lay.addLayout(ch_wrap)

        if step.get('action'):
            act = step['action']
            btn = QPushButton("  " + act['label'])
            btn.setIcon(IconRenderer.icon(act.get('icon', 'chat'), 18, QColor(t['text_primary'])))
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(230)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._primary_btn())
            btn.clicked.connect(lambda _=False, a=act['do'], b=btn: self._do_action(a, b))
            wrap = QHBoxLayout()
            wrap.addStretch()
            wrap.addWidget(btn)
            wrap.addStretch()
            lay.addLayout(wrap)

        if step.get('hint'):
            hint = QLabel("Astuce : " + step['hint'])
            hint.setAlignment(Qt.AlignCenter)
            hint.setWordWrap(True)
            hint.setStyleSheet(f"""
                color:{t['text_secondary']}; font-size:10px; font-style:italic;
                background-color:{t['bg_secondary']}; border-radius:6px; padding:9px 12px;
            """)
            lay.addWidget(hint)

        lay.addStretch()
        return page

    def _primary_btn(self):
        t = self.theme
        return f"""
            QPushButton {{
                background-color:{t['accent']}; color:{t['text_primary']};
                border:none; border-radius:8px; padding:8px 18px; font-weight:bold;
            }}
            QPushButton:hover {{ background-color:{t['accent_hover']}; }}
        """

    def _secondary_btn(self):
        t = self.theme
        return f"""
            QPushButton {{
                background-color:{t['bg_secondary']}; color:{t['text_primary']};
                border:1px solid {t['border']}; border-radius:8px; padding:8px 16px;
            }}
            QPushButton:hover {{
                background-color:{t['accent_hover']}; border:1px solid {t['border_focus']};
            }}
            QPushButton:disabled {{ color:{t['text_secondary']}; }}
        """

    # ------------------------------------------------------------------
    def _show_step(self, index):
        if index < 0 or index >= len(self.STEPS):
            return
        self.current = index
        step = self.STEPS[index]
        self.stack.setCurrentIndex(index)
        self.progress_bar.setValue(index)
        self.progress_label.setText(f"Étape {index + 1} / {len(self.STEPS)}")
        self.prev_btn.setEnabled(index > 0)
        if step.get('final'):
            self.next_btn.setText("Terminer")
            self.skip_btn.setVisible(False)
        else:
            self.next_btn.setText("Suivant")
            self.skip_btn.setVisible(True)
        self._update_halo(step)
        if step.get('final'):
            self._celebrate()

    def _update_halo(self, step):
        if self.halo:
            self.halo.stop()
            self.halo = None
        if step.get('halo') and self.main_window:
            self.halo = PulseHaloWidget(self.main_window, color=self.theme['accent'])
            self.halo.show()

    def _do_action(self, action, button=None):
        if action == 'discord':
            QDesktopServices.openUrl(QUrl(DISCORD_INVITE))
        elif action == 'channel':
            QApplication.clipboard().setText("manifest-generator")
            if button:
                old = button.text()
                button.setText("  Copié !")
                QTimer.singleShot(1500, lambda: button.setText(old))

    def _next(self):
        if self.current >= len(self.STEPS) - 1:
            self._finish()
        else:
            self._show_step(self.current + 1)

    def _prev(self):
        if self.current > 0:
            self._show_step(self.current - 1)

    def _celebrate(self):
        if self.confetti:
            return
        self.confetti = ConfettiWindow(self.theme)
        geo = self.geometry()
        self.confetti.setGeometry(geo)
        self.confetti.show()
        self.confetti.start()

    def _finish(self):
        self.config['tutorial_shown'] = self.dont_show.isChecked()
        save_config(self.config)
        if self.halo:
            self.halo.stop()
            self.halo = None
        if self.confetti:
            self.confetti.stop()
            self.confetti = None
        self.accept()

    # ---- Déplacement de la fenêtre frameless ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            if self.confetti:
                self.confetti.setGeometry(self.geometry())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def closeEvent(self, event):
        if self.halo:
            self.halo.stop()
        if self.confetti:
            self.confetti.stop()
        super().closeEvent(event)
