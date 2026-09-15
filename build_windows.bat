@echo off
echo ========================================
echo    Cherry Inventario - Compilar .exe
echo ========================================
echo.

echo [1/4] Verificando PyInstaller...
python -m PyInstaller --version
if %errorlevel% neq 0 (
    echo PyInstaller no encontrado. Instalando...
    pip install pyinstaller
)

echo.
echo [2/4] Creando icono...
python create_icon.py

echo.
echo [3/4] Compilando .exe...
python -m Pyinstaller CherryInventario.spec

echo.
echo [4/4] Creando archivo zip...
powershell Compress-Archive -Path "dist\CherryInventario" -DestinationPath "CherryInventario.zip" -Force

echo.
echo ========================================
echo    ¡Compilacion completada!
echo ========================================
echo.
echo Archivos generados:
echo   - dist\CherryInventario\ (carpeta con el .exe)
echo   - CherryInventario.zip (para GitHub Release)
echo.
echo Para subir a GitHub Release:
echo   1. Ve a https://github.com/DELIVERYEXPRESS25/CHERRY2026/releases
echo   2. Click "Create a new release"
echo   3. Sube CherryInventario.zip
echo.
pause
