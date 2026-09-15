#!/usr/bin/env python3
"""
Auto-Updater for Cherry Inventario
Downloads updates from GitHub releases automatically
"""
import os
import sys
import json
import shutil
import zipfile
import hashlib
import base64
import urllib.request
import urllib.error
import tempfile
import time
from datetime import datetime

GITHUB_REPO = "DELIVERYEXPRESS25/CHERRY2026"
VERSION_FILE = "version.json"
LOCAL_VERSION = "1.1.0"

def simple_hash(password):
    salt = "cherry_salt_2024"
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return base64.b64encode(pwdhash).decode('utf-8')

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_version():
    version_path = os.path.join(get_base_dir(), VERSION_FILE)
    if os.path.exists(version_path):
        try:
            with open(version_path, 'r') as f:
                data = json.load(f)
                return data.get('version', LOCAL_VERSION)
        except:
            return LOCAL_VERSION
    return LOCAL_VERSION

def save_version(version):
    version_path = os.path.join(get_base_dir(), VERSION_FILE)
    with open(version_path, 'w') as f:
        json.dump({
            'version': version,
            'updated_at': datetime.now().isoformat()
        }, f, indent=2)

def check_github_update():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={'User-Agent': 'CherryUpdater'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            tag = data.get('tag_name', '').replace('v', '')
            description = data.get('body', '')
            published = data.get('published_at', '')
            
            assets = data.get('assets', [])
            source_url = None
            for asset in assets:
                if asset['name'] == 'source_code':
                    source_url = asset['browser_download_url']
                    break
            
            if not source_url:
                source_url = data.get('zipball_url')
            
            return {
                'version': tag,
                'description': description,
                'published': published,
                'download_url': source_url
            }
    except Exception as e:
        print(f"Error checking updates: {e}")
        return None

def download_and_extract(download_url, target_dir):
    try:
        print(f"Descargando actualizacion...")
        req = urllib.request.Request(download_url, headers={'User-Agent': 'CherryUpdater'})
        with urllib.request.urlopen(req, timeout=30) as response:
            zip_data = response.read()
        
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'update.zip')
        
        with open(zip_path, 'wb') as f:
            f.write(zip_data)
        
        print("Extrayendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d)) and d.startswith('DELIVERYEXPRESS25')]
        
        if extracted_dirs:
            source_dir = os.path.join(temp_dir, extracted_dirs[0])
        else:
            source_dir = temp_dir
        
        for item in ['templates', 'static', 'app.py']:
            src = os.path.join(source_dir, item)
            dst = os.path.join(target_dir, item)
            
            if os.path.exists(src):
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                print(f"Actualizado: {item}")
        
        shutil.rmtree(temp_dir)
        return True
        
    except Exception as e:
        print(f"Error downloading update: {e}")
        return False

def check_and_update():
    base_dir = get_base_dir()
    current_version = get_version()
    
    print(f"Cherry Inventario - Version actual: {current_version}")
    print("Buscando actualizaciones...")
    
    update_info = check_github_update()
    
    if not update_info:
        print("No se pudo verificar actualizaciones")
        return False
    
    remote_version = update_info['version']
    
    if remote_version and remote_version != current_version:
        print(f"Nueva version disponible: {remote_version}")
        print(f"Descripcion: {update_info['description'][:100]}...")
        
        if update_info['download_url']:
            if download_and_extract(update_info['download_url'], base_dir):
                save_version(remote_version)
                print(f"Actualizado a version {remote_version}")
                return True
        
        return False
    else:
        print("Tienes la ultima version")
        return False

if __name__ == '__main__':
    if check_and_update():
        print("Reiniciando aplicacion...")
        if getattr(sys, 'frozen', False):
            os.execl(sys.executable, sys.executable, *sys.argv)
        else:
            os.execl(sys.executable, sys.executable, *sys.argv)
