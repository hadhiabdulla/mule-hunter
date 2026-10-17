"""Tiny local web server (standard library). Serves the UI and three JSON endpoints."""
import json
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import accounts, live, upload
from .export import RESULTS

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_BODY = 60 * 1024 * 1024


def summarise(res, extra=None):
    A = res["accounts"]
    ranked = sorted(A.values(), key=lambda r: -r["risk"])
    return {
        "summary": {"accounts": len(A), "transactions": len(res["tx"]),
                    "high_risk": sum(1 for r in ranked if r["risk"] >= 60),
                    "medium_risk": sum(1 for r in ranked if 40 <= r["risk"] < 60),
                    "round_trips": res["cycles"]},
        "top": [{k: r[k] for k in ("account", "risk", "reasons", "received", "sent", "tx_in", "tx_out", "chain")}
                for r in ranked[:60]],
        "network": accounts.network(res), **(extra or {})}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(STATIC, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/api/elliptic":
            p = os.path.join(RESULTS, "elliptic.json")
            if not os.path.exists(p):
                return self._send(404, {"error": "No Elliptic results yet. Run: python run.py --download "
                                                 "then python run.py --elliptic"})
            with open(p, "rb") as f:
                return self._send(200, f.read())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BODY:
                return self._send(413, {"error": "File too large for the local demo (60 MB max)."})
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/upload/preview":
                header, sample = upload.read_header(body["csv"])
                return self._send(200, {"header": header, "sample": sample,
                                        "mapping": upload.guess_mapping(header)})
            if self.path == "/api/upload/analyse":
                tx, rep = upload.parse(body["csv"], body.get("mapping"))
                res = accounts.analyse(tx, reporting_limit=float(body.get("limit") or 10000))
                return self._send(200, summarise(res, {"report": rep}))
            if self.path == "/api/live":
                nb = max(1, min(int(body.get("blocks", 6)), 10))
                pb = max(25, min(int(body.get("per_block", 100)), 300))
                edges, info = live.fetch(nb, pb, log=lambda *a: None)
                res = accounts.analyse(edges, relay_window_h=6)
                return self._send(200, summarise(res, {"live": info}))
            self._send(404, {"error": "not found"})
        except (ValueError, KeyError) as e:
            self._send(400, {"error": str(e)})
        except RuntimeError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:       # keep the server alive
            traceback.print_exc()
            self._send(500, {"error": f"Unexpected error: {e}"})

    def log_message(self, *a):
        pass


def serve(port=8000):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"Mule Hunter running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
