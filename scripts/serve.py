# -*- coding: utf-8 -*-
"""Local HTTP server: serve ROOT (GET) + accept frame uploads (POST /save?p=...)."""
import sys, os, urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SAVEDIR = sys.argv[2] if len(sys.argv) > 2 else ROOT
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8791
LOG = os.path.join(SAVEDIR, 'serve.log')

class H(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _safe(self, rel):
        rel = rel.replace('\\', '/').lstrip('/')
        parts = [p for p in rel.split('/') if p not in ('', '.', '..')]
        return os.path.join(*parts) if parts else None

    def do_POST(self):
        try:
            q = urllib.parse.urlparse(self.path)
            if q.path != '/save':
                self.send_error(404)
                return
            params = urllib.parse.parse_qs(q.query)
            rel = (params.get('p') or [''])[0]
            n = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(n)
            dst = self._safe(rel)
            if dst is None:
                self.send_error(400)
                return
            dst = os.path.join(SAVEDIR, dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + '.tmp%d' % os.getpid()
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, dst)
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'ok')
        except Exception as e:
            try:
                with open(LOG, 'a', encoding='utf-8') as f:
                    f.write("POST-ERR %r\n" % (e,))
            except Exception:
                pass
            try:
                self.send_error(500)
            except Exception:
                pass

    def do_GET(self):
        if self.path == '/ping':
            self.send_response(200); self.send_header('Content-Length', '4')
            self.end_headers(); self.wfile.write(b'pong'); return
        return super().do_GET()

    def log_message(self, *a):
        pass

ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer.request_queue_size = 128
ThreadingHTTPServer.allow_reuse_address = True
httpd = ThreadingHTTPServer(('127.0.0.1', PORT), H)
print(f"serving {ROOT} on http://127.0.0.1:{PORT}/  save-root={SAVEDIR}", flush=True)
httpd.serve_forever()
