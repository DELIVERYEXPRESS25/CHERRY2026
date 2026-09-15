import os
import sys
import json
import hashlib
import subprocess
import urllib.request
import zipfile
import shutil
import tempfile
from datetime import datetime

GITHUB_REPO = "DELIVERYEXPRESS25/CHERRY"
CURRENT_VERSION = "1.0.0"
APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

def get_current_version():
    version_file = os.path.join(APP_DIR, "version.txt")
    if os.path.exists(version_file):
        return open(version_file).read().strip()
    return CURRENT_VERSION

def save_version(version):
    with open(os.path.join(APP_DIR, "version.txt"), "w") as f:
        f.write(version)

def check_github_releases():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": "CherryInventario",
            "Accept": "application/vnd.github.v3+json"
        })
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read())
        
        version = data.get("tag_name", "").lstrip("v")
        description = data.get("body", "")
        published = data.get("published_at", "")
        
        download_url = None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break
        
        return {
            "version": version,
            "description": description,
            "published_at": published,
            "download_url": download_url,
            "html_url": data.get("html_url", ""),
            "prerelease": data.get("prerelease", False)
        }
    except Exception as e:
        print(f"Error al verificar GitHub: {e}")
        return None

def download_and_install(download_url, expected_version):
    try:
        print(f"Descargando versión {expected_version}...")
        
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "update.zip")
        
        req = urllib.request.Request(download_url, headers={"User-Agent": "CherryInventario"})
        response = urllib.request.urlopen(req, timeout=60)
        
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(response, f)
        
        print("Instalando...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(APP_DIR)
        
        save_version(expected_version)
        
        shutil.rmtree(temp_dir)
        
        print(f"Actualizado a versión {expected_version}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def create_github_release(version, changes, zip_path):
    print(f"\nPara publicar en GitHub:")
    print(f"1. Ve a: https://github.com/{GITHUB_REPO}/releases/new")
    print(f"2. Tag: v{version}")
    print(f"3. Title: Cherry Inventario v{version}")
    print(f"4. Description:")
    print(f"\n## Cambios en v{version}\n")
    for change in changes:
        print(f"- {change}")
    print(f"\n5. Sube el archivo: {zip_path}")
    print(f"6. Publica el release")

if __name__ == "__main__":
    print("=" * 50)
    print("  Cherry Inventario - Auto-Actualizador")
    print(f"  Versión actual: {get_current_version()}")
    print("=" * 50)
    
    release = check_github_releases()
    
    if release:
        latest = release["version"]
        current = get_current_version()
        
        print(f"\nÚltima versión: {latest}")
        print(f"Tu versión: {current}")
        
        if latest > current:
            print(f"\n¡Nueva versión disponible!")
            print(f"Fecha: {release['published_at']}")
            print(f"\nCambios:\n{release['description']}")
            
            if release["download_url"]:
                response = input("\n¿Actualizar ahora? (s/n): ")
                if response.lower() == 's':
                    if download_and_install(release["download_url"], latest):
                        print("\nReiniciando...")
                        os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                print("\nNo hay archivo .zip en el release")
                print(f"Descarga manual: {release['html_url']}")
        else:
            print("\nTienes la última versión.")
    else:
        print("\nNo se pudo verificar actualizaciones")
    
    print()
