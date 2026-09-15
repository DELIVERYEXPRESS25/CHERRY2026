#!/bin/bash
# ============================================
#   Cherry Inventario - Publicar Versión
# ============================================

echo "========================================"
echo "  Cherry Inventario - Publicar Versión"
echo "========================================"
echo

# Pedir versión
echo "¿Qué versión? (ejemplo: 1.1.0)"
read -r VERSION

if [ -z "$VERSION" ]; then
    echo "Error: Debes escribir una versión"
    exit 1
fi

# Pedir cambios
echo "Describe los cambios (presiona Enter vacío para terminar):"
CAMBIOS=""
while true; do
    read -r CAMBIO
    if [ -z "$CAMBIO" ]; then
        break
    fi
    CAMBIOS="$CAMBIOS- $CAMBIO\n"
done

echo
echo "========================================"
echo "  Versión: $VERSION"
echo "  Cambios:"
echo -e "$CAMBIOS"
echo "========================================"
echo

# Actualizar version.txt
echo "$VERSION" > version.txt

# Crear commit
echo "1. Creando commit..."
git add .
git commit -m "Release v$VERSION"

# Crear tag
echo "2. Creando tag v$VERSION..."
git tag -a "v$VERSION" -m "Release v$VERSION"

# Subir
echo "3. Subiendo a GitHub..."
git push
git push --tags

echo
echo "========================================"
echo "  ¡Versión $VERSION publicada!"
echo ""
echo "  Siguiente paso:"
echo "  1. Ve a: https://github.com/DELIVERYEXPRESS25/CHERRY2026/releases/new"
echo "  2. Selecciona el tag: v$VERSION"
echo "  3. Sube el archivo .zip como Asset"
echo "  4. Publica el release"
echo "========================================"
