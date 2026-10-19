#!/usr/bin/env python3
import os
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("HUNTER_TOKEN", "vnc9k2m4")
PORT = int(os.environ.get("HUNTER_PORT", "8080"))


def run(cmd):
    try:
        p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=180)
        return "$ %s\n\n%s\n[stderr]\n%s\n[exit %s]" % (cmd, p.stdout, p.stderr, p.returncode)
    except Exception as e:
        return "error: %s" % e


class H(BaseHTTPRequestHandler):
    def send(self, text, code=200):
        body = text.encode("utf-8", "replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path

        if p == "/ping":
            return self.send("pong")

        if (q.get("token") or [""])[0] != TOKEN:
            return self.send("bad token", 403)

        if p == "/run":
            return self.send(run((q.get("cmd") or [""])[0]))

        if p == "/deploy":
            name = (q.get("file") or [""])[0]
            code = (q.get("code") or [""])[0]
            if not name:
                return self.send("no file", 400)
            full = os.path.join(ROOT, name)
            d = os.path.dirname(full)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(code)
            out = run("git add -A && git -c user.email=a@b.c -c user.name=agent commit -m 'deploy %s' ; git push" % name)
            return self.send("ok, wrote %s (%s chars)\n\n%s" % (name, len(code), out))

        if p == "/read":
            try:
                with open(os.path.join(ROOT, (q.get("file") or [""])[0]), encoding="utf-8") as f:
                    return self.send(f.read())
            except Exception as e:
                return self.send("error: %s" % e, 404)

        if p == "/status":
            return self.send(run("hostname; uptime; free -m | head -2; df -h / | tail -1; ls -la"))

        return self.send("unknown", 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("listening on :%s" % PORT)
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
