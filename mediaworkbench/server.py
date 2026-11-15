"""JSON HTTP interface for an operator-controlled media service."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from . import assets, db, timeline, renders

class Handler(BaseHTTPRequestHandler):
    def respond(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        try:
            path = urlparse(self.path).path.strip('/').split('/')
            with db.connect(self.server.database) as conn:
                if len(path) == 2 and path[0] == 'projects': result = timeline.snapshot(conn, int(path[1]))
                elif len(path) == 2 and path[0] == 'renders': result = renders.get(conn, int(path[1]))
                else: return self.respond(404, {'error':'not found'})
            self.respond(200,result)
        except (ValueError, OSError) as exc: self.respond(400, {'error':str(exc)})
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 65536: raise ValueError('invalid request size')
            data = json.loads(self.rfile.read(length))
            with db.connect(self.server.database) as conn:
                if self.path == '/assets': result = assets.register(conn, data['path'])
                elif self.path == '/projects': result = timeline.project(conn, data['name'])
                elif self.path == '/clips': result = timeline.add_clip(conn, data['project_id'], data['asset_id'], data['start_ms'], data['end_ms'], data.get('gain',1))
                elif self.path == '/renders': result = renders.create(conn, data['project_id'], data['destination'])
                else: return self.respond(404, {'error':'not found'})
            self.respond(201,result)
        except (ValueError, OSError, KeyError, TypeError) as exc: self.respond(400, {'error':str(exc)})

def serve():
    server = ThreadingHTTPServer(('127.0.0.1', int(os.getenv('MEDIA_PORT','8765'))), Handler)
    server.database = os.getenv('MEDIA_DATABASE','media-workbench.sqlite3')
    print(f'Listening on http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()

if __name__ == '__main__': serve()
