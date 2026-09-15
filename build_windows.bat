@echo off
echo ========================================
echo   Cherry Inventario - Build Windows EXE
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python no encontrado. Instale Python 3.9+ desde python.org
    pause
    exit /b 1
)

REM Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Compilando...
pyinstaller --name "CherryInventario" --onedir --windowed ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import werkzeug ^
  --hidden-import jinja2 ^
  --hidden-import sqlalchemy ^
  app.py

echo.
echo ========================================
echo   Build completado!
echo   Ejecutable en: dist\CherryInventario\
echo ========================================
echo.
pause
