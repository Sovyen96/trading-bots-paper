"""Dashboard local: sirve dashboard.html y el estado en vivo en el puerto 8800.

Uso:  python dashboard.py   ->  abre http://localhost:8800
"""
import http.server
import json
import os

from config import BASE_DIR, STATE_PATH

PORT = 8800


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/dashboard.html"
        if self.path == "/state.json":
            try:
                with open(STATE_PATH, "rb") as f:
                    body = f.read()
            except FileNotFoundError:
                body = json.dumps({"error": "Aún no hay estado. Ejecuta live.py"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    print(f"Dashboard en http://localhost:{PORT}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
