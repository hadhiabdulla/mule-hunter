"""Unit tests on tiny hand-built examples (the real data is only used by run.py)."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mulehunter import accounts, graph, upload
from mulehunter.forest import RandomForest
from mulehunter.iforest import IsolationForest
from mulehunter.model import auc, pr_auc, Logistic

T0 = datetime(2026, 1, 1)


def tx(a, b, amt, h, label=None):
    return {"src": a, "dst": b, "amount": amt, "ts": T0 + timedelta(hours=h), "label": label}


def background(n=60):
    import random
    r = random.Random(0)
    return [tx(f"P{r.randrange(30)}", f"Q{r.randrange(15)}", r.uniform(5, 200), r.uniform(0, 400))
            for _ in range(n)]


class Accounts(unittest.TestCase):
    def test_relay_chain_flagged(self):
        rows = background()
        for k in range(6):
            h = 10 + k * 20
            rows += [tx(f"V{k}", "M1", 1000, h), tx("M1", "M2", 950, h + 0.5), tx("M2", "BOSS", 900, h + 1)]
        res = accounts.analyse(rows)["accounts"]
        self.assertGreater(res["M1"]["risk"], 50)
        self.assertGreater(res["M2"]["risk"], 50)
        self.assertLess(res["V0"]["risk"], 40)          # victims are not accused

    def test_round_trip_cycle(self):
        rows = background() + [tx("A", "B", 1000, 1), tx("B", "C", 970, 3), tx("C", "A", 940, 6)]
        out = accounts.analyse(rows)
        self.assertGreaterEqual(out["cycles"], 1)
        self.assertGreater(out["accounts"]["A"]["signals"]["cycle"], 0)

    def test_labels_taint_downstream_only(self):
        rows = background() + [tx("V", "MULE", 500, 1, label=1), tx("MULE", "NEXT", 480, 2)]
        res = accounts.analyse(rows)["accounts"]
        self.assertGreaterEqual(res["MULE"]["risk"], 90)
        self.assertGreater(res["NEXT"]["signals"]["taint"], 0)
        self.assertEqual(res["V"]["signals"]["taint"], 0)

    def test_structuring(self):
        rows = background() + [tx(f"X{i}", "S", 9500 + i, 5 + i) for i in range(5)]
        self.assertGreater(accounts.analyse(rows)["accounts"]["S"]["signals"]["structure"], 0.5)


class Upload(unittest.TestCase):
    CSV = "From,To,Amount,Date,is_fraud\n" + "\n".join(
        f"A{i},B{i},{10 + i},2026-02-0{1 + i % 9} 10:00:00,{i % 2}" for i in range(12))

    def test_auto_mapping(self):
        header, _ = upload.read_header(self.CSV)
        m = upload.guess_mapping(header)
        self.assertEqual(m, {"sender": 0, "receiver": 1, "amount": 2, "timestamp": 3, "label": 4})

    def test_parse_and_validate(self):
        rows, rep = upload.parse(self.CSV)
        self.assertEqual(len(rows), 12)
        bad = self.CSV + "\nA1,A1,5,2026-02-01,0\nA2,B2,-4,2026-02-01,0\nA3,B3,x,2026-02-01,0\nA4,B4,5,notadate,0"
        rows, rep = upload.parse(bad)
        self.assertEqual(rep["rows_skipped"], 4)

    def test_missing_columns(self):
        with self.assertRaises(ValueError):
            upload.parse("a,b\n1,2\n")


class Graph(unittest.TestCase):
    def test_relay_chain_and_taint(self):
        g = graph.Graph(list("abcde"), [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])
        chains = graph.relay_chains(g)
        self.assertEqual(chains["b"][0], 3)
        down, up = graph.taint(g, ["a"], hops=3, decay=0.5)
        self.assertGreater(down["b"], down["c"])
        self.assertEqual(up["b"], 0)


class Models(unittest.TestCase):
    def test_forest_separates(self):
        import random
        r = random.Random(1)
        X = [[r.gauss(0, 1), r.gauss(0, 1)] for _ in range(300)] + [[r.gauss(4, 1), r.gauss(4, 1)] for _ in range(300)]
        y = [0] * 300 + [1] * 300
        rf = RandomForest(trees=10, depth=5, mtry=2, sample=300).fit(X, y)
        self.assertGreater(rf.predict([4, 4]), 0.8)
        self.assertLess(rf.predict([0, 0]), 0.2)

    def test_isolation_forest_flags_outlier(self):
        import random
        r = random.Random(2)
        X = [[r.gauss(0, 1), r.gauss(0, 1)] for _ in range(300)]
        f = IsolationForest(trees=60).fit(X)
        self.assertGreater(f.score([9, 9]), f.score([0, 0]))

    def test_metrics(self):
        self.assertAlmostEqual(auc([0.1, 0.9, 0.8, 0.2], [0, 1, 1, 0]), 1.0)
        self.assertAlmostEqual(pr_auc([0.1, 0.9, 0.8, 0.2], [0, 1, 1, 0]), 1.0)
        lr = Logistic(1, epochs=30).fit([[0.0], [1.0], [0.1], [0.9]] * 20, [0, 1, 0, 1] * 20)
        self.assertGreater(lr.predict([1.0]), lr.predict([0.0]))


if __name__ == "__main__":
    unittest.main()
