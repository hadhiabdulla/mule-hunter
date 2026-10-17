"""End-to-end check of the upload feature through the real HTTP server.

TEST DATA ONLY: the CSV below is made up for the test (including deliberately bad rows).
It is not used for any reported result.
"""
import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mulehunter import web, watchlists

GOOD = [f"A{i % 20},B{i % 9},{20 + i},2026-03-0{1 + i % 9} 1{i % 10}:00:00,0" for i in range(60)]
CHAIN = []
for k in range(6):
    d = f"2026-03-1{k} "
    CHAIN += [f"V{k},MULE1,1000,{d}09:00:00,1", f"MULE1,MULE2,950,{d}09:30:00,", f"MULE2,BOSS,900,{d}10:00:00,"]
BAD = ["X1,X1,5,2026-03-01 10:00:00,0", "X2,Y2,-4,2026-03-01 10:00:00,0",
       "X3,Y3,abc,2026-03-01 10:00:00,0", "X4,Y4,5,not-a-date,0", ",Y5,5,2026-03-01 10:00:00,0"]


def make_csv(header):
    return header + "\n" + "\n".join(GOOD + CHAIN + BAD)


class UploadEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        watchlists._cache.update(at=9e12, data={"ofac": set(), "scam": set(), "errors": []})  # no network
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), web.H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_autodetected_columns(self):
        csv = make_csv("sender,receiver,amount,timestamp,label")
        _, prev = self.post("/api/upload/preview", {"csv": csv})
        self.assertEqual(prev["mapping"], {"sender": 0, "receiver": 1, "amount": 2, "timestamp": 3, "label": 4})
        code, out = self.post("/api/upload/analyse", {"csv": csv, "mapping": prev["mapping"]})
        self.assertEqual(code, 200)
        self.assertEqual(out["report"]["rows_skipped"], len(BAD))
        top = [r["account"] for r in out["top"][:3]]
        self.assertIn("MULE2", top)
        self.assertIn("watch", out)

    def test_manual_mapping_with_odd_headers(self):
        csv = make_csv("c1,c2,c3,c4,c5")
        _, prev = self.post("/api/upload/preview", {"csv": csv})
        self.assertEqual(prev["mapping"], {})           # nothing to guess
        code, out = self.post("/api/upload/analyse", {"csv": csv})
        self.assertEqual(code, 400)                     # asks for a mapping
        m = {"sender": 0, "receiver": 1, "amount": 2, "timestamp": 3, "label": 4}
        code, out = self.post("/api/upload/analyse", {"csv": csv, "mapping": m})
        self.assertEqual(code, 200)
        self.assertGreater(out["summary"]["accounts"], 20)

    def test_garbage_file(self):
        code, out = self.post("/api/upload/analyse", {"csv": "hello\nworld\n"})
        self.assertEqual(code, 400)
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
