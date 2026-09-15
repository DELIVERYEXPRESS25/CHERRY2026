@echo off
echo ============================================
echo   Cherry Inventario - Publicar Versión
echo ============================================
echo

set /p VERSION="¿Qué versión? (ejemplo: 1.1.0) "

if "%VERSION%"=="" (
    echo Error: Debes escribir una versión
    pause
    exit /b 1
)

echo.
echo Describe los cambios (presiona Enter vacío para terminar):
set CAMBIOS=
:loop
set /p CAMBIO="- "
if "%CAMBIO%"=="" goto done
set CAMBIOS=%CAMBIOS% - %CAMBIO%
goto loop
:done

echo.
echo ============================================
echo  Versión: %VERSION%
echo  Cambios:%CAMBIOS%
echo ============================================
echo.

echo %VERSION% > version.txt

echo 1. Creando commit...
git add .
git commit -m "Release v%VERSION%"

echo 2. Creando tag v%VERSION%...
git tag -a "v%VERSION%" -m "Release v%VERSION%"

echo 3. Subiendo a GitHub...
git push
git push --tags

echo.
echo ============================================
echo  ¡Versión %VERSION% publicada!
echo.
echo  Siguiente paso:
echo  1. Ve a: https://github.com/DELIVERYEXPRESS25/CHERRY2026/releases/new
echo  2. Selecciona el tag: v%VERSION%
echo  3. Sube el archivo .zip como Asset
echo  4. Publica el release
echo ============================================
pause
