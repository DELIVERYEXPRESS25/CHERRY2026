#!/usr/bin/env python3
"""
Script para crear releases en GitHub
Uso: python github_release.py <version> "cambio1" "cambio2" ...
"""

import os
import sys
import json
import subprocess
import zipfile
import hashlib
from datetime import datetime
from pathlib import Path

GITHUB_REPO = "DELIVERYEXPRESS25/CHERRY"

def create_release(version, changes):
    print(f"\n{'='*50}")
    print(f"  Creando release v{version}")
    print(f"{'='*50}\n")
    
    zip_name = f"CherryInventario_{version}.zip"
    
    print("1. Creando paquete...")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        files_to_include = [
            "app.py",
            "requirements.txt",
            "updater.py",
            "templates/",
            "static/",
            "instance/"
        ]
        
        for item in files_to_include:
            if os.path.isfile(item):
                zipf.write(item)
                print(f"   + {item}")
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, ".")
                        zipf.write(file_path, arcname)
                        print(f"   + {arcname}")
    
    with open(zip_name, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    with open("version.txt", "w") as f:
        f.write(version)
    
    print(f"\n2. Paquete creado: {zip_name}")
    print(f"   Hash: {file_hash}")
    
    print(f"\n3. Subiendo a Git...")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Release v{version}"], check=True)
    subprocess.run(["git", "tag", f"v{version}"], check=True)
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "--tags"], check=True)
    
    print(f"\n4. Crea el release manualmente en GitHub:")
    print(f"   https://github.com/{GITHUB_REPO}/releases/new")
    print(f"\n   Tag: v{version}")
    print(f"   Title: Cherry Inventario v{version}")
    print(f"\n   Description:")
    print(f"   ## Cambios en v{version}\n")
    for change in changes:
        print(f"   - {change}")
    print(f"\n   Sube: {zip_name}")
    
    print(f"\n{'='*50}")
    print(f"  ¡Listo! Los usuarios recibirán la actualización")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python github_release.py <versión> \"cambio1\" \"cambio2\" ...")
        print("Ejemplo: python github_release.py 1.1.0 \"Corregido bug en facturas\" \"Nuevo reporte\"")
        sys.exit(1)
    
    version = sys.argv[1]
    changes = sys.argv[2:]
    
    create_release(version, changes)
