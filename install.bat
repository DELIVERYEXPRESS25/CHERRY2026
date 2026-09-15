@echo off
echo ========================================
echo    Cherry Inventario - Instalacion
echo ========================================
echo.

echo [1/3] Instalando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error al instalar dependencias
    pause
    exit /b 1
)

echo.
echo [2/3] Creando base de datos...
python -c "from app import init_db; init_db()"

echo.
echo [3/3] Creando acceso directo...
echo @echo off > "%USERPROFILE%\Desktop\Cherry Inventario.bat"
echo cd "%~dp0" >> "%USERPROFILE%\Desktop\Cherry Inventario.bat"
echo python app.py >> "%USERPROFILE%\Desktop\Cherry Inventario.bat"
echo pause >> "%USERPROFILE%\Desktop\Cherry Inventario.bat"

echo.
echo ========================================
echo    ¡Instalacion completada!
echo ========================================
echo.
echo Ahora puedes ejecutar "Cherry Inventario.bat"
echo desde tu escritorio o ejecutar: python app.py
echo.
echo Abrira automaticamente el navegador en:
echo http://127.0.0.1:5000
echo.
pause
