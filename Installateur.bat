@echo off
chcp 65001 >nul
title FurryTools - Installateur
cd /d "%~dp0"

echo.
echo  ============================================
echo   FurryTools - Installateur
echo  ============================================
echo.
echo   Logiciels installes :
echo    - Python 3.10       https://www.python.org
echo    - SteamTools 1.8.30 https://www.steamtools.net
echo.
echo  Ouverture de l'interface graphique...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File "%~dp0Installateur.ps1"

if %errorlevel% neq 0 (
    echo.
    echo  [ERREUR] L'installateur graphique n'a pas pu s'ouvrir.
    echo.
    echo  Solutions possibles :
    echo   1. Clic droit sur ce fichier ^> "Executer en tant qu'administrateur"
    echo   2. Ou ouvrez PowerShell et tapez :
    echo      Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
    echo      puis relancez ce fichier.
    echo.
    pause
)
