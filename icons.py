"""Rendu d'icônes vectorielles via QPainter — aucune dépendance à des emojis.

Chaque icône est dessinée programmatiquement sur un QPixmap transparent.
Utilisation :
    pixmap = IconRenderer.render('paw', 80, QColor('#ffffff'))
    icon = IconRenderer.icon('book', 24, QColor('#ffffff'))   # -> QIcon
"""
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (QPixmap, QPainter, QPen, QBrush, QColor, QPainterPath,
                         QIcon, QPolygonF)


class IconRenderer:

    @staticmethod
    def render(name, size=80, color=None):
        if color is None:
            color = QColor('#ffffff')
        elif isinstance(color, str):
            color = QColor(color)

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        method = getattr(IconRenderer, f"_draw_{name}", None)
        if method is None:
            method = IconRenderer._draw_paw
        try:
            method(painter, size, color)
        finally:
            painter.end()
        return pixmap

    @staticmethod
    def icon(name, size=24, color=None):
        return QIcon(IconRenderer.render(name, size, color))

    # ----- Helpers -----
    @staticmethod
    def _stroke(painter, color, width):
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

    @staticmethod
    def _fill(painter, color):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))

    # ===================== ICÔNES =====================

    @staticmethod
    def _draw_paw(painter, s, color):
        """Empreinte de patte (logo / bienvenue)."""
        IconRenderer._fill(painter, color)
        # Coussinet principal
        painter.drawEllipse(QRectF(s * 0.27, s * 0.46, s * 0.46, s * 0.40))
        # 4 doigts
        toes = [
            (s * 0.18, s * 0.34, s * 0.15, s * 0.20),
            (s * 0.36, s * 0.20, s * 0.15, s * 0.22),
            (s * 0.55, s * 0.20, s * 0.15, s * 0.22),
            (s * 0.70, s * 0.34, s * 0.15, s * 0.20),
        ]
        for x, y, w, h in toes:
            painter.drawEllipse(QRectF(x, y, w, h))

    @staticmethod
    def _draw_mouse(painter, s, color):
        """Souris d'ordinateur (clic droit)."""
        w = s * 0.10
        IconRenderer._stroke(painter, color, w)
        body = QRectF(s * 0.30, s * 0.14, s * 0.40, s * 0.66)
        painter.drawRoundedRect(body, s * 0.20, s * 0.20)
        # Séparation gauche/droite
        painter.drawLine(QPointF(s * 0.50, s * 0.14), QPointF(s * 0.50, s * 0.42))
        painter.drawLine(QPointF(s * 0.30, s * 0.42), QPointF(s * 0.70, s * 0.42))
        # Molette
        IconRenderer._fill(painter, color)
        painter.drawRoundedRect(QRectF(s * 0.465, s * 0.20, s * 0.07, s * 0.13),
                                s * 0.03, s * 0.03)

    @staticmethod
    def _draw_keyboard(painter, s, color):
        """Clavier (saisie de texte)."""
        w = s * 0.075
        IconRenderer._stroke(painter, color, w)
        painter.drawRoundedRect(QRectF(s * 0.12, s * 0.30, s * 0.76, s * 0.40),
                                s * 0.06, s * 0.06)
        IconRenderer._fill(painter, color)
        key = s * 0.055
        gap_x = s * 0.135
        start_x = s * 0.24
        for row, y in enumerate((s * 0.40, s * 0.52)):
            for i in range(4):
                painter.drawRoundedRect(
                    QRectF(start_x + i * gap_x, y, key, key), s * 0.012, s * 0.012)
        # Barre d'espace
        painter.drawRoundedRect(QRectF(s * 0.32, s * 0.61, s * 0.36, s * 0.045),
                                s * 0.015, s * 0.015)

    @staticmethod
    def _draw_pointer(painter, s, color):
        """Curseur / flèche de sélection (double-clic)."""
        IconRenderer._fill(painter, color)
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.18)
        path.lineTo(s * 0.28, s * 0.78)
        path.lineTo(s * 0.43, s * 0.63)
        path.lineTo(s * 0.53, s * 0.84)
        path.lineTo(s * 0.62, s * 0.80)
        path.lineTo(s * 0.52, s * 0.59)
        path.lineTo(s * 0.70, s * 0.59)
        path.closeSubpath()
        painter.drawPath(path)

    @staticmethod
    def _draw_clipboard(painter, s, color):
        """Presse-papiers (copier la commande)."""
        w = s * 0.07
        IconRenderer._stroke(painter, color, w)
        painter.drawRoundedRect(QRectF(s * 0.26, s * 0.18, s * 0.48, s * 0.66),
                                s * 0.06, s * 0.06)
        # Pince du haut
        IconRenderer._fill(painter, color)
        painter.drawRoundedRect(QRectF(s * 0.40, s * 0.10, s * 0.20, s * 0.14),
                                s * 0.04, s * 0.04)
        # Lignes de texte
        IconRenderer._stroke(painter, color, s * 0.05)
        for y in (s * 0.40, s * 0.53, s * 0.66):
            painter.drawLine(QPointF(s * 0.36, y), QPointF(s * 0.64, y))

    @staticmethod
    def _draw_chat(painter, s, color):
        """Bulle de discussion (Discord)."""
        w = s * 0.07
        IconRenderer._stroke(painter, color, w)
        bubble = QRectF(s * 0.15, s * 0.20, s * 0.70, s * 0.48)
        painter.drawRoundedRect(bubble, s * 0.12, s * 0.12)
        # Queue de la bulle
        IconRenderer._fill(painter, color)
        tail = QPolygonF([
            QPointF(s * 0.32, s * 0.66),
            QPointF(s * 0.30, s * 0.82),
            QPointF(s * 0.46, s * 0.66),
        ])
        painter.drawPolygon(tail)
        # Points
        for x in (s * 0.34, s * 0.50, s * 0.66):
            painter.drawEllipse(QPointF(x, s * 0.44), s * 0.035, s * 0.035)

    @staticmethod
    def _draw_send(painter, s, color):
        """Avion en papier (envoyer)."""
        IconRenderer._fill(painter, color)
        plane = QPolygonF([
            QPointF(s * 0.14, s * 0.50),
            QPointF(s * 0.86, s * 0.18),
            QPointF(s * 0.54, s * 0.86),
            QPointF(s * 0.46, s * 0.58),
        ])
        painter.drawPolygon(plane)
        IconRenderer._stroke(painter, QColor(0, 0, 0, 90), s * 0.03)
        painter.drawLine(QPointF(s * 0.46, s * 0.58), QPointF(s * 0.86, s * 0.18))

    @staticmethod
    def _draw_download(painter, s, color):
        """Flèche de téléchargement."""
        w = s * 0.085
        IconRenderer._stroke(painter, color, w)
        painter.drawLine(QPointF(s * 0.50, s * 0.16), QPointF(s * 0.50, s * 0.60))
        path = QPainterPath()
        path.moveTo(s * 0.33, s * 0.45)
        path.lineTo(s * 0.50, s * 0.63)
        path.lineTo(s * 0.67, s * 0.45)
        painter.drawPath(path)
        painter.drawLine(QPointF(s * 0.24, s * 0.80), QPointF(s * 0.76, s * 0.80))

    @staticmethod
    def _draw_target(painter, s, color):
        """Cible (zone de drop)."""
        w = s * 0.075
        IconRenderer._stroke(painter, color, w)
        c = QPointF(s * 0.5, s * 0.5)
        painter.drawEllipse(c, s * 0.34, s * 0.34)
        painter.drawEllipse(c, s * 0.21, s * 0.21)
        IconRenderer._fill(painter, color)
        painter.drawEllipse(c, s * 0.08, s * 0.08)

    @staticmethod
    def _draw_trophy(painter, s, color):
        """Coupe / trophée (succès)."""
        w = s * 0.07
        IconRenderer._stroke(painter, color, w)
        cup = QPainterPath()
        cup.moveTo(s * 0.32, s * 0.20)
        cup.lineTo(s * 0.68, s * 0.20)
        cup.lineTo(s * 0.64, s * 0.46)
        cup.cubicTo(s * 0.62, s * 0.58, s * 0.38, s * 0.58, s * 0.36, s * 0.46)
        cup.closeSubpath()
        painter.drawPath(cup)
        # Anses
        painter.drawArc(QRectF(s * 0.16, s * 0.20, s * 0.20, s * 0.24),
                        90 * 16, 180 * 16)
        painter.drawArc(QRectF(s * 0.64, s * 0.20, s * 0.20, s * 0.24),
                        -90 * 16, 180 * 16)
        # Pied
        painter.drawLine(QPointF(s * 0.50, s * 0.56), QPointF(s * 0.50, s * 0.70))
        painter.drawLine(QPointF(s * 0.36, s * 0.80), QPointF(s * 0.64, s * 0.80))
        painter.drawLine(QPointF(s * 0.42, s * 0.70), QPointF(s * 0.58, s * 0.70))

    @staticmethod
    def _draw_check(painter, s, color):
        """Coche dans un cercle."""
        w = s * 0.085
        IconRenderer._stroke(painter, color, w)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.38, s * 0.38)
        path = QPainterPath()
        path.moveTo(s * 0.32, s * 0.52)
        path.lineTo(s * 0.45, s * 0.65)
        path.lineTo(s * 0.70, s * 0.36)
        painter.drawPath(path)

    @staticmethod
    def _draw_book(painter, s, color):
        """Livre ouvert (tutoriel)."""
        w = s * 0.07
        IconRenderer._stroke(painter, color, w)
        # Reliure
        painter.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.50, s * 0.80))
        # Page gauche
        left = QPainterPath()
        left.moveTo(s * 0.50, s * 0.24)
        left.cubicTo(s * 0.36, s * 0.16, s * 0.22, s * 0.18, s * 0.16, s * 0.22)
        left.lineTo(s * 0.16, s * 0.74)
        left.cubicTo(s * 0.22, s * 0.70, s * 0.36, s * 0.68, s * 0.50, s * 0.80)
        painter.drawPath(left)
        # Page droite
        right = QPainterPath()
        right.moveTo(s * 0.50, s * 0.24)
        right.cubicTo(s * 0.64, s * 0.16, s * 0.78, s * 0.18, s * 0.84, s * 0.22)
        right.lineTo(s * 0.84, s * 0.74)
        right.cubicTo(s * 0.78, s * 0.70, s * 0.64, s * 0.68, s * 0.50, s * 0.80)
        painter.drawPath(right)

    @staticmethod
    def _draw_copy(painter, s, color):
        """Deux feuilles superposées (copier)."""
        w = s * 0.07
        IconRenderer._stroke(painter, color, w)
        painter.drawRoundedRect(QRectF(s * 0.22, s * 0.16, s * 0.40, s * 0.48),
                                s * 0.05, s * 0.05)
        painter.drawRoundedRect(QRectF(s * 0.38, s * 0.36, s * 0.40, s * 0.48),
                                s * 0.05, s * 0.05)

    @staticmethod
    def _draw_close(painter, s, color):
        """Croix de fermeture."""
        w = s * 0.12
        IconRenderer._stroke(painter, color, w)
        painter.drawLine(QPointF(s * 0.30, s * 0.30), QPointF(s * 0.70, s * 0.70))
        painter.drawLine(QPointF(s * 0.70, s * 0.30), QPointF(s * 0.30, s * 0.70))

    @staticmethod
    def _draw_arrow_left(painter, s, color):
        w = s * 0.12
        IconRenderer._stroke(painter, color, w)
        painter.drawLine(QPointF(s * 0.70, s * 0.50), QPointF(s * 0.30, s * 0.50))
        path = QPainterPath()
        path.moveTo(s * 0.46, s * 0.34)
        path.lineTo(s * 0.30, s * 0.50)
        path.lineTo(s * 0.46, s * 0.66)
        painter.drawPath(path)

    @staticmethod
    def _draw_arrow_right(painter, s, color):
        w = s * 0.12
        IconRenderer._stroke(painter, color, w)
        painter.drawLine(QPointF(s * 0.30, s * 0.50), QPointF(s * 0.70, s * 0.50))
        path = QPainterPath()
        path.moveTo(s * 0.54, s * 0.34)
        path.lineTo(s * 0.70, s * 0.50)
        path.lineTo(s * 0.54, s * 0.66)
        painter.drawPath(path)
