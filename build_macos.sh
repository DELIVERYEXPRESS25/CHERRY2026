#!/bin/bash
echo "========================================"
echo "  Cherry Inventario - Build macOS App"
echo "========================================"
echo

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "Python3 no encontrado. Instale desde python.org"
    exit 1
fi

# Instalar dependencias
echo "Instalando dependencias..."
pip3 install -r requirements.txt
pip3 install pyinstaller

echo
echo "Compilando..."
pyinstaller --name "CherryInventario" --onedir --windowed \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --hidden-import werkzeug \
  --hidden-import jinja2 \
  --hidden-import sqlalchemy \
  app.py

echo
echo "========================================"
echo "  Build completado!"
echo "  App en: dist/CherryInventario.app"
echo "========================================"
echo
