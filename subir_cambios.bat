@echo off
echo ============================================
echo   Cherry Inventario - Subir Cambios a GitHub
echo ============================================
echo

set /p MENSAJE="¿Qué cambiaste? "

if "%MENSAJE%"=="" (
    echo Error: Debes escribir un mensaje
    pause
    exit /b 1
)

echo.
echo Agregando archivos...
git add .

echo Creando commit...
git commit -m "%MENSAJE%"

echo Subiendo a GitHub...
git push

echo.
echo ============================================
echo   ¡Cambios subidos!
echo   https://github.com/DELIVERYEXPRESS25/CHERRY2026
echo ============================================
pause
