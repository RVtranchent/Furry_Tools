# ================================================================
# Exemple de plugin FurryTools - Demonstration complete
# ================================================================
# Copiez ce fichier, renommez-le (ex: mon_plugin.py)
# et modifiez-le pour creer votre propre plugin.
# Les fichiers commencant par _ sont ignores.
# ================================================================

PLUGIN_NAME        = "Exemple"
PLUGIN_VERSION     = "1.0.0"
PLUGIN_AUTHOR      = "rvmillions"
PLUGIN_DESCRIPTION = "Plugin de demonstration fourni avec FurryTools"


def register(app):
    """
    Appelee au demarrage de FurryTools.

    Parametre : app (FurryTools)
        app.config         -> dict : configuration utilisateur
        app.steam_folder   -> str  : dossier Steam detecte
        app.steam_path     -> str  : chemin de steam.exe
        app.target_folder  -> str  : dossier stplug-in (manifests)
        app.game_names     -> dict : cache { appid: nom_du_jeu }

    Retourne : list[QAction]  (actions dans le menu Plugins)
    """
    from PyQt5.QtWidgets import QAction

    a1 = QAction("Infos installation")
    a1.triggered.connect(lambda: infos_installation(app))

    a2 = QAction("Copier le chemin Steam")
    a2.triggered.connect(lambda: copier_chemin_steam(app))

    a3 = QAction("Compter les manifests")
    a3.triggered.connect(lambda: compter_manifests(app))

    return [a1, a2, a3]


# ── Fonctions des actions ─────────────────────────────────────────────────────

def infos_installation(app):
    from PyQt5.QtWidgets import QMessageBox
    lignes = [
        "Plugin   : " + PLUGIN_NAME + " v" + PLUGIN_VERSION,
        "Steam    : " + (app.steam_folder or "Non detecte"),
        "Manifests: " + (app.target_folder or "Non trouve"),
        "Jeux     : " + str(len(app.game_names)) + " en cache",
        "Theme    : " + app.config.get("theme", "?"),
    ]
    QMessageBox.information(None, PLUGIN_NAME, "\n".join(lignes))


def copier_chemin_steam(app):
    from PyQt5.QtWidgets import QApplication, QMessageBox
    if not app.steam_folder:
        QMessageBox.warning(None, PLUGIN_NAME, "Steam non detecte.")
        return
    QApplication.clipboard().setText(app.steam_folder)
    QMessageBox.information(
        None, PLUGIN_NAME,
        "Chemin copie :\n" + app.steam_folder
    )


def compter_manifests(app):
    import os
    from PyQt5.QtWidgets import QMessageBox
    if not app.target_folder or not os.path.exists(app.target_folder):
        QMessageBox.warning(None, PLUGIN_NAME, "Dossier SteamTools non trouve.")
        return
    fichiers = [f for f in os.listdir(app.target_folder) if f.endswith(".lua")]
    QMessageBox.information(
        None, PLUGIN_NAME,
        str(len(fichiers)) + " manifest(s) trouves\ndans : " + app.target_folder
    )
