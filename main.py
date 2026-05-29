"""Furry Tools — point d'entrée.

Lancement :  python main.py
"""
import os
import sys

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer

from utils import install_excepthook, single_instance_check, release_instance_mutex
from core import FurryTools


def main():
    install_excepthook()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # IMPORTANT : empêche l'app de se fermer quand le tutoriel (ou un dialog) se ferme,
    # car le logo flottant est une fenêtre de type Qt.Tool que Qt ignore.
    app.setQuitOnLastWindowClosed(False)

    if not single_instance_check():
        QMessageBox.critical(None, "Erreur", "Furry Tools est déjà en cours d'exécution.")
        return

    # Libérer le mutex proprement à la sortie
    app.aboutToQuit.connect(release_instance_mutex)

    window = FurryTools()
    window.show()

    if window.config.get('auto_launch_steam', False) and window.steam_path and os.path.exists(window.steam_path):
        QTimer.singleShot(500, window.restart_steam)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
