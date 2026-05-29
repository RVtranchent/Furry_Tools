"""Fonctions utilitaires de Furry Tools."""
import os
import sys
import ctypes
import traceback
from datetime import datetime

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont

from config import CONFIG_DIR

# Handle global du mutex (gardé en vie pour toute la durée du process)
_INSTANCE_MUTEX = None


def install_excepthook():
    def _hook(exctype, value, tb):
        error_msg = ''.join(traceback.format_exception(exctype, value, tb))
        log_dir = os.path.join(CONFIG_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"Date: {datetime.now()}\n")
                f.write(f"Python: {sys.version}\n")
                f.write(f"OS: {sys.platform}\n\n")
                f.write(error_msg)
        except Exception:
            pass
        try:
            QMessageBox.critical(None, "Erreur inattendue",
                                 f"Une erreur est survenue. Un log a été créé :\n{log_file}\n\n{str(value)[:200]}")
        except Exception:
            pass
        sys.__excepthook__(exctype, value, tb)
    sys.excepthook = _hook


def center_window(window):
    frame = window.frameGeometry()
    screen = QApplication.primaryScreen().availableGeometry().center()
    frame.moveCenter(screen)
    window.move(frame.topLeft())


def get_scaled_size(base_width, base_height, config=None):
    if config and 'dialog_width' in config:
        return config['dialog_width'], config['dialog_height']
    return base_width, base_height


def get_scaled_font(base_size=10, base_family='Segoe UI'):
    screen = QApplication.primaryScreen()
    if not screen:
        return QFont(base_family, base_size)
    scale = max(1.0, screen.logicalDotsPerInch() / 96.0)
    return QFont(base_family, max(8, int(base_size * scale)))


def single_instance_check():
    """Empêche plusieurs instances. Garde le handle vivant proprement."""
    global _INSTANCE_MUTEX
    if not sys.platform.startswith('win'):
        return True
    mutex_name = "FurryTools_Instance_Mutex"
    _INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
        _INSTANCE_MUTEX = None
        return False
    return True


def release_instance_mutex():
    global _INSTANCE_MUTEX
    if _INSTANCE_MUTEX and sys.platform.startswith('win'):
        try:
            ctypes.windll.kernel32.ReleaseMutex(_INSTANCE_MUTEX)
            ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
        except Exception:
            pass
        _INSTANCE_MUTEX = None


def _startup_key():
    import winreg
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Microsoft\Windows\CurrentVersion\Run",
                          0, winreg.KEY_SET_VALUE)


def add_to_startup():
    try:
        import winreg
        key = _startup_key()
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        winreg.SetValueEx(key, "FurryTools", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def remove_from_startup():
    try:
        import winreg
        key = _startup_key()
        winreg.DeleteValue(key, "FurryTools")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def is_in_startup():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "FurryTools")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False
