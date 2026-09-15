#!/bin/bash
# ============================================
#   Cherry Inventario - Subir Cambios a GitHub
# ============================================

echo "========================================"
echo "  Cherry Inventario - Subir Cambios"
echo "========================================"
echo

# Pedir mensaje de commit
echo "¿Qué cambiaste? (ejemplo: Corregido bug en facturas)"
read -r MENSAJE

if [ -z "$MENSAJE" ]; then
    echo "Error: Debes escribir un mensaje"
    exit 1
fi

echo
echo "Agregando archivos..."
git add .

echo "Creando commit..."
git commit -m "$MENSAJE"

echo "Subiendo a GitHub..."
git push

echo
echo "========================================"
echo "  ¡Cambios subidos!"
echo "  https://github.com/DELIVERYEXPRESS25/CHERRY2026"
echo "========================================"
