#!/usr/bin/env python3
"""
Script para publicar actualizaciones de Cherry Inventario
Ejecutar en el servidor de actualizaciones
"""

import os
import sys
import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

def calculate_hash(file_path):
    """Calcular hash SHA256 de un archivo"""
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def create_release(version, changes, app_dir=".", output_dir="releases"):
    """Crear una nueva versión para distribución"""
    
    print(f"Creando versión {version}...")
    
    # Crear directorio de salida
    os.makedirs(output_dir, exist_ok=True)
    
    # Crear paquete de actualización
    import zipfile
    
    package_name = f"CherryInventario_{version}.zip"
    package_path = os.path.join(output_dir, package_name)
    
    files_to_include = [
        "app.py",
        "requirements.txt",
        "templates/",
        "static/",
        "updater.py"
    ]
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in files_to_include:
            item_path = os.path.join(app_dir, item)
            if os.path.isfile(item_path):
                zipf.write(item_path, item)
            elif os.path.isdir(item_path):
                for root, dirs, files in os.walk(item_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, app_dir)
                        zipf.write(file_path, arcname)
    
    # Calcular hash
    file_hash = calculate_hash(package_path)
    
    # Crear changelog
    changelog = {
        "version": version,
        "release_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "description": "\n".join(changes),
        "download_url": f"https://tudominio.com/updates/{package_name}",
        "hash": file_hash,
        "mandatory": False,
        "changelog": changes
    }
    
    # Guardar changelog
    changelog_path = os.path.join(output_dir, "version.json")
    with open(changelog_path, 'w') as f:
        json.dump(changelog, f, indent=2, ensure_ascii=False)
    
    print(f"\nVersión {version} creada:")
    print(f"  Paquete: {package_path}")
    print(f"  Hash: {file_hash}")
    print(f"  Changelog: {changelog_path}")
    
    return package_path, file_hash

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python publish_update.py <versión>")
        print("Ejemplo: python publish_update.py 1.1.0")
        sys.exit(1)
    
    version = sys.argv[1]
    
    print("=" * 50)
    print("  Cherry Inventario - Publicar Actualización")
    print("=" * 50)
    print()
    
    # Pedir cambios
    changes = []
    print("Ingrese los cambios (línea vacía para terminar):")
    while True:
        change = input("  - ")
        if not change:
            break
        changes.append(change)
    
    if not changes:
        print("Error: Debe especificar al menos un cambio")
        sys.exit(1)
    
    # Crear release
    create_release(version, changes)
    
    print()
    print("=" * 50)
    print("  Instrucciones:")
    print("  1. Subir los archivos a tu servidor web")
    print("  2. Actualizar version.json en el servidor")
    print("  3. Los usuarios recibirán la actualización automáticamente")
    print("=" * 50)
