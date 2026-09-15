#!/bin/bash
echo "========================================"
echo "   Cherry Inventario - Instalacion"
echo "========================================"
echo ""

echo "[1/3] Instalando dependencias..."
pip3 install -r requirements.txt

echo ""
echo "[2/3] Creando base de datos..."
python3 -c "from app import init_db; init_db()"

echo ""
echo "[3/3] Creando acceso directo en el Escritorio..."
cat > ~/Desktop/"Cherry Inventario.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 app.py
EOF
chmod +x ~/Desktop/"Cherry Inventario.command"

echo ""
echo "========================================"
echo "   ¡Instalacion completada!"
echo "========================================"
echo ""
echo "Ahora puedes ejecutar 'Cherry Inventario'"
echo "desde tu Escritorio o ejecutar: python3 app.py"
echo ""
echo "Abrira automaticamente el navegador en:"
echo "http://127.0.0.1:5000"
echo ""
