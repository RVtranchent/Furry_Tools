"""Système de plugins de FurryTools.

Chaque fichier .py placé dans le dossier plugins/ est chargé au démarrage.
Les fichiers commençant par _ sont ignorés.
"""
import os
import sys
import importlib.util
import traceback

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")

# ---------------------------------------------------------------------------
# Contenu des fichiers créés lors de la première initialisation
# ---------------------------------------------------------------------------
_README = """\
====================================================
  FurryTools - Guide de création de plugins
====================================================

Chaque fichier .py placé dans ce dossier est chargé
automatiquement au démarrage de FurryTools.
Les fichiers commençant par _ sont ignorés.

----------------------------------------------------
STRUCTURE MINIMALE D'UN PLUGIN
----------------------------------------------------

  PLUGIN_NAME        = "Nom affiché dans le menu"
  PLUGIN_VERSION     = "1.0.0"
  PLUGIN_AUTHOR      = "Votre pseudo"
  PLUGIN_DESCRIPTION = "Ce que fait ce plugin"

  def register(app):
      from PyQt5.QtWidgets import QAction
      action = QAction("Mon action")
      action.triggered.connect(ma_fonction)
      return [action]          # liste de QAction

  def ma_fonction():
      from PyQt5.QtWidgets import QMessageBox
      QMessageBox.information(None, "Plugin", "Bonjour !")

----------------------------------------------------
ATTRIBUTS DISPONIBLES VIA app
----------------------------------------------------

  app.config          dict  - Configuration utilisateur
  app.steam_folder    str   - Dossier Steam détecté
  app.steam_path      str   - Chemin de steam.exe
  app.target_folder   str   - Dossier stplug-in (manifests)
  app.game_names      dict  - Cache {appid: nom_du_jeu}

----------------------------------------------------
RETOUR DE register()
----------------------------------------------------

  - Retournez une liste de QAction.
  - Chaque action s'affiche dans le menu "Plugins".
  - Retournez [] si votre plugin n'ajoute rien au menu.

----------------------------------------------------
EXEMPLE
----------------------------------------------------

  Voir le fichier exemple_plugin.py dans ce dossier.

----------------------------------------------------
NOTES
----------------------------------------------------

  - Redémarrez FurryTools après avoir ajouté un plugin.
  - Les erreurs de chargement sont affichées dans les
    logs (%APPDATA%\\FurryTools\\logs\\).

====================================================
"""

_EXEMPLE = """\
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
    \"\"\"
    Appelee au demarrage de FurryTools.

    Parametre : app (FurryTools)
        app.config         -> dict : configuration utilisateur
        app.steam_folder   -> str  : dossier Steam detecte
        app.steam_path     -> str  : chemin de steam.exe
        app.target_folder  -> str  : dossier stplug-in (manifests)
        app.game_names     -> dict : cache { appid: nom_du_jeu }

    Retourne : list[QAction]  (actions dans le menu Plugins)
    \"\"\"
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
    QMessageBox.information(None, PLUGIN_NAME, "\\n".join(lignes))


def copier_chemin_steam(app):
    from PyQt5.QtWidgets import QApplication, QMessageBox
    if not app.steam_folder:
        QMessageBox.warning(None, PLUGIN_NAME, "Steam non detecte.")
        return
    QApplication.clipboard().setText(app.steam_folder)
    QMessageBox.information(
        None, PLUGIN_NAME,
        "Chemin copie :\\n" + app.steam_folder
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
        str(len(fichiers)) + " manifest(s) trouves\\ndans : " + app.target_folder
    )
"""


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def ensure_plugins_dir():
    """Crée le dossier plugins/ et les fichiers de démarrage si absents."""
    os.makedirs(PLUGINS_DIR, exist_ok=True)

    readme = os.path.join(PLUGINS_DIR, "LISEZ_MOI.txt")
    if not os.path.exists(readme):
        try:
            with open(readme, "w", encoding="utf-8") as f:
                f.write(_README)
        except OSError:
            pass

    # exemple_plugin.py est toujours ecrase : c'est un fichier de reference,
    # pas un plugin utilisateur. Pour personnaliser, le renommer d'abord.
    exemple = os.path.join(PLUGINS_DIR, "exemple_plugin.py")
    try:
        with open(exemple, "w", encoding="utf-8") as f:
            f.write(_EXEMPLE)
    except OSError:
        pass


def load_plugins(app):
    """
    Charge tous les plugins du dossier plugins/.

    Retourne une liste de dicts :
        {name, version, author, description, actions}
    """
    ensure_plugins_dir()
    loaded = []

    try:
        filenames = sorted(os.listdir(PLUGINS_DIR))
    except OSError:
        return loaded

    for fname in filenames:
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(PLUGINS_DIR, fname)
        try:
            spec = importlib.util.spec_from_file_location(fname[:-3], path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            info = {
                "name":    getattr(mod, "PLUGIN_NAME",        fname[:-3]),
                "version": getattr(mod, "PLUGIN_VERSION",     "?"),
                "author":  getattr(mod, "PLUGIN_AUTHOR",      "?"),
                "desc":    getattr(mod, "PLUGIN_DESCRIPTION", ""),
                "actions": [],
            }
            if hasattr(mod, "register"):
                result = mod.register(app)
                if result:
                    info["actions"] = list(result)
            loaded.append(info)
        except Exception:
            print(f"[Plugins] Erreur lors du chargement de {fname} :")
            traceback.print_exc()

    return loaded
