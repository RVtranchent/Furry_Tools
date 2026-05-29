"""Chargeur de themes personnalises pour FurryTools.

Les themes sont des fichiers .json places dans le dossier themes/.
"""
import os
import json

THEMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")

REQUIRED_KEYS = [
    'bg_primary', 'bg_secondary', 'bg_tertiary',
    'text_primary', 'text_secondary',
    'border', 'border_focus',
    'accent', 'accent_hover',
]

# ---------------------------------------------------------------------------
# Contenu des fichiers generes au premier demarrage
# ---------------------------------------------------------------------------
_README = """\
====================================================
  FurryTools - Guide de creation de themes
====================================================

Placez vos fichiers .json dans ce dossier.
Ils apparaitront dans le menu Themes du clic droit.

----------------------------------------------------
STRUCTURE D'UN THEME (.json)
----------------------------------------------------

{
    "name":          "Nom de mon theme",
    "bg_primary":    "#1a1a2e",
    "bg_secondary":  "#16213e",
    "bg_tertiary":   "#0f3460",
    "text_primary":  "#e0e0e0",
    "text_secondary":"#b0b0b0",
    "border":        "#444466",
    "border_focus":  "#6666aa",
    "accent":        "#5555cc",
    "accent_hover":  "#7777dd"
}

----------------------------------------------------
ROLE DE CHAQUE COULEUR
----------------------------------------------------

bg_primary    -> Fond principal des fenetres et menus
bg_secondary  -> Fond secondaire (items, zones sombres)
bg_tertiary   -> Fond tertiaire (survol, selections)
text_primary  -> Texte principal
text_secondary-> Texte secondaire, labels discrets
border        -> Bordures des elements
border_focus  -> Bordures au focus / element actif
accent        -> Couleur principale (boutons, barre prog.)
accent_hover  -> Couleur au survol des elements accent

----------------------------------------------------
REGLES
----------------------------------------------------

- Toutes les couleurs sont en hexadecimal (#rrggbb).
- Le champ "name" definit le nom dans le menu.
  S'il est absent, le nom du fichier est utilise.
- Les fichiers commencant par _ sont ignores.
- Utilisez "Recharger les themes" dans le menu pour
  voir les nouveaux themes sans redemarrer.

----------------------------------------------------
EXEMPLE
----------------------------------------------------

Voir le fichier exemple_theme.json dans ce dossier.

====================================================
"""

_EXEMPLE_JSON = """\
{
    "name": "Minuit bleu",
    "bg_primary":    "#0d1117",
    "bg_secondary":  "#161b22",
    "bg_tertiary":   "#21262d",
    "text_primary":  "#e6edf3",
    "text_secondary":"#8b949e",
    "border":        "#30363d",
    "border_focus":  "#58a6ff",
    "accent":        "#1f6feb",
    "accent_hover":  "#388bfd"
}
"""


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def ensure_themes_dir():
    """Cree le dossier themes/ et les fichiers de demarrage si absents."""
    os.makedirs(THEMES_DIR, exist_ok=True)

    readme = os.path.join(THEMES_DIR, "LISEZ_MOI.txt")
    if not os.path.exists(readme):
        try:
            with open(readme, "w", encoding="utf-8") as f:
                f.write(_README)
        except OSError:
            pass

    exemple = os.path.join(THEMES_DIR, "exemple_theme.json")
    if not os.path.exists(exemple):
        try:
            with open(exemple, "w", encoding="utf-8") as f:
                f.write(_EXEMPLE_JSON)
        except OSError:
            pass


def load_custom_themes():
    """
    Charge tous les fichiers .json du dossier themes/.

    Retourne un dict { nom_theme: theme_dict }.
    Les themes invalides (cles manquantes, JSON invalide) sont ignores.
    """
    ensure_themes_dir()
    themes = {}

    try:
        filenames = sorted(os.listdir(THEMES_DIR))
    except OSError:
        return themes

    for fname in filenames:
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        path = os.path.join(THEMES_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            name = data.get("name", fname[:-5])
            missing = [k for k in REQUIRED_KEYS if k not in data]
            if missing:
                print(f"[Themes] {fname}: cles manquantes {missing} - ignore")
                continue

            themes[name] = {k: data[k] for k in REQUIRED_KEYS}
        except Exception as e:
            print(f"[Themes] Erreur chargement {fname}: {e}")

    return themes
