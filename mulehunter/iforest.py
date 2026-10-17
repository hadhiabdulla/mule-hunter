"""Isolation Forest implemented from scratch (Liu et al., 2008). Pure Python."""
import math
import random


def _c(n):
    if n <= 1:
        return 0.0
    return 2.0 * (math.log(n - 1) + 0.5772156649) - 2.0 * (n - 1) / n


class _Node:
    __slots__ = ("f", "v", "l", "r", "size")


def _build(rows, depth, limit, rnd):
    n = _Node()
    n.size = len(rows)
    n.f = None
    if depth >= limit or len(rows) <= 1:
        return n
    nf = len(rows[0])
    for _ in range(8):
        f = rnd.randrange(nf)
        lo, hi = min(r[f] for r in rows), max(r[f] for r in rows)
        if hi > lo:
            v = rnd.uniform(lo, hi)
            n.f, n.v = f, v
            n.l = _build([r for r in rows if r[f] < v], depth + 1, limit, rnd)
            n.r = _build([r for r in rows if r[f] >= v], depth + 1, limit, rnd)
            return n
    return n


def _path(node, x):
    d = 0
    while node.f is not None:
        node = node.l if x[node.f] < node.v else node.r
        d += 1
    return d + _c(node.size)


class IsolationForest:
    def __init__(self, trees=60, sample=256, seed=3):
        self.trees, self.sample, self.rnd = trees, sample, random.Random(seed)

    def fit(self, X):
        s = min(self.sample, len(X))
        limit = math.ceil(math.log2(max(s, 2)))
        self.s = s
        self.forest = [_build(self.rnd.sample(X, s), 0, limit, self.rnd) for _ in range(self.trees)]
        return self

    def score(self, x):
        e = sum(_path(t, x) for t in self.forest) / len(self.forest)
        return 2 ** (-e / _c(self.s))
