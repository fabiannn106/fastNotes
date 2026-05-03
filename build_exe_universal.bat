@echo off
title Fast Notes - EXE Builder
echo ============================================
echo  Fast Notes - Automatischer EXE-Builder
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden!
    pause & exit /b 1
)

echo [1/4] Python gefunden - installiere Abhaengigkeiten...
python -m pip install customtkinter keyboard pystray Pillow flask pyinstaller --quiet
if errorlevel 1 (
    echo [FEHLER] Installation fehlgeschlagen!
    pause & exit /b 1
)

echo [2/4] Abhaengigkeiten installiert!
echo.
echo [3/4] Erstelle EXE - bitte warten ca. 1-2 Minuten...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "FastNotes" ^
    --collect-all customtkinter ^
    --collect-all pystray ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import flask ^
    --hidden-import werkzeug ^
    --noconfirm ^
    fast_notes.py

echo.
if exist "dist\FastNotes.exe" (
    echo ============================================
    echo  FERTIG! EXE liegt hier:
    echo  %CD%\dist\FastNotes.exe
    echo ============================================
    echo.
    echo App jetzt starten? [J/N]
    set /p ANS=
    if /i "%ANS%"=="J" start "" "%CD%\dist\FastNotes.exe"
) else (
    echo [FEHLER] EXE wurde nicht erstellt. Lies die Fehlermeldungen oben.
)
pause
