"""Gestion de la configuration et du cache de Furry Tools."""
import os
import sys
import json

# Dossier d'installation de l'application (là où vivent les .py et version.txt)
APP_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'FurryTools')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
CACHE_FILE = os.path.join(CONFIG_DIR, 'cache.json')
DISCORD_CLIENT_ID = "1482031246463996127"
DISCORD_INVITE = "https://discord.gg/Wx7wP9fmUf"
REPO_URL = "https://github.com/RVtranchent/Furry_Tools"
VERSION_URL = "https://raw.githubusercontent.com/RVtranchent/Furry_Tools/main/version.txt"
API_URL = "https://api.github.com/repos/RVtranchent/Furry_Tools/releases/latest"
# Archive ZIP de la branche main pour l'installation de la mise à jour
UPDATE_ZIP_URL = "https://github.com/RVtranchent/Furry_Tools/archive/refs/heads/main.zip"

os.makedirs(CONFIG_DIR, exist_ok=True)


def get_current_version():
    try:
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        version_file = os.path.join(base, "version.txt")
        if os.path.exists(version_file):
            # utf-8-sig : ignore un éventuel BOM en tête (sinon la comparaison
            # de versions casse, ex: "﻿1.1.0").
            with open(version_file, 'r', encoding='utf-8-sig') as f:
                v = f.read().strip()
                if v:
                    return v
    except Exception:
        pass
    return "1.1.0"


CURRENT_VERSION = get_current_version()


DEFAULT_CONFIG = {
    'icon_size': 150,
    'private_games': [],
    'logo_path': '',
    'enable_discord_rpc': False,
    'font_size': 10,
    'font_family': 'Segoe UI',
    'grid_columns': 2,
    'grid_width': 400,
    'grid_max_height': 500,
    'button_min_width': 180,
    'button_max_width': 250,
    'button_height': 40,
    'name_max_length': 40,
    'dialog_width': 600,
    'dialog_height': 600,
    'theme': 'Violet profond',
    'start_with_windows': False,
    'auto_launch_steam': False,
    'auto_check_updates': True,
    'auto_add_all_dlc': False,
    'tutorial_shown': False
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config.pop('private_password_hash', None)
            config.pop('discord_client_id', None)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_copy = dict(config)
    config_copy.pop('private_password_hash', None)
    config_copy.pop('discord_client_id', None)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_copy, f, indent=4)
    except Exception:
        pass


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4)
    except Exception:
        pass
