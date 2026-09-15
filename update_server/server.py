#!/usr/bin/env python3
"""
Servidor de actualizaciones para Cherry Inventario
Ejecutar en un servidor web o usar como servicio
"""

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

class UpdateHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/version.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            version_file = os.path.join(os.path.dirname(__file__), 'version.json')
            if os.path.exists(version_file):
                with open(version_file, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(json.dumps({
                    "version": "1.0.0",
                    "error": "No version info available"
                }).encode())
        else:
            super().do_GET()

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, UpdateHandler)
    print(f"Servidor de actualizaciones corriendo en puerto {port}")
    print(f"URL: http://localhost:{port}")
    print("Presiona Ctrl+C para detener")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
