"""
Biogenie — Serveur web + moniteur GTC
Lance le dashboard sur un vrai port HTTP et le moniteur en arrière-plan.
"""
import threading, http.server, os, logging, time
from monitor import run_check, INTERVAL_MIN
import schedule

PORT = int(os.environ.get("PORT", 8080))

log = logging.getLogger(__name__)

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence les logs HTTP

def start_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Dashboard disponible sur le port {PORT}")
    httpd.serve_forever()

def start_monitor():
    run_check()
    schedule.every(INTERVAL_MIN).minutes.do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    # Lance le moniteur en arrière-plan
    t = threading.Thread(target=start_monitor, daemon=True)
    t.start()
    # Lance le serveur web (bloquant)
    start_server()
