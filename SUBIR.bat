@echo off
echo ========================================
echo    Subiendo cambios a GitHub...
echo ========================================
echo.

cd C:\Users\carloignacio\Documents\CHERRY

echo [1/3] Agregando archivos...
git add .

echo [2/3] Creando commit...
set /p MENSAJE="Escribe la descripcion: "
git commit -m "%MENSAJE%"

echo [3/3] Subiendo a GitHub...
git push origin master:main

echo.
echo ========================================
echo    ¡Cambios subidos!
echo ========================================
echo.
pause
