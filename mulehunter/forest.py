"""Random Forest classifier from scratch (histogram splits, Gini, balanced bootstrap). Pure Python."""
import random
from bisect import bisect_right


class RandomForest:
    def __init__(self, trees=40, depth=9, bins=14, mtry=14, sample=9000, min_leaf=8, seed=2):
        self.n_trees, self.depth, self.bins = trees, depth, bins
        self.mtry, self.sample, self.min_leaf = mtry, sample, min_leaf
        self.rnd = random.Random(seed)

    def fit(self, X, y):
        nf = len(X[0])
        self.cuts = []
        for f in range(nf):
            col = sorted(r[f] for r in X)
            cs = sorted({col[int(len(col) * q / self.bins)] for q in range(1, self.bins)})
            self.cuts.append(cs)
        B = [[bisect_right(self.cuts[f], r[f]) for r in X] for f in range(nf)]  # column-major
        pos = [i for i, t in enumerate(y) if t]
        neg = [i for i, t in enumerate(y) if not t]
        self.trees = []
        half = self.sample // 2
        for _ in range(self.n_trees):
            idx = [self.rnd.choice(pos) for _ in range(half)] + \
                  [self.rnd.choice(neg) for _ in range(half)]
            self.trees.append(self._grow(B, y, idx, 0, nf))
        return self

    def _grow(self, B, y, idx, d, nf):
        p = sum(y[i] for i in idx)
        n = len(idx)
        if d >= self.depth or n < 2 * self.min_leaf or p == 0 or p == n:
            return p / n
        best = None
        for f in self.rnd.sample(range(nf), min(self.mtry, nf)):
            col = B[f]
            nb = len(self.cuts[f]) + 1
            cnt, cp = [0] * nb, [0] * nb
            for i in idx:
                b = col[i]
                cnt[b] += 1
                cp[b] += y[i]
            ln = lp = 0
            for b in range(nb - 1):
                ln += cnt[b]
                lp += cp[b]
                rn, rp = n - ln, p - lp
                if ln < self.min_leaf or rn < self.min_leaf:
                    continue
                g = ln * (1 - (lp / ln) ** 2 - ((ln - lp) / ln) ** 2) + \
                    rn * (1 - (rp / rn) ** 2 - ((rn - rp) / rn) ** 2)
                if best is None or g < best[0]:
                    best = (g, f, b)
        if best is None:
            return p / n
        _, f, b = best
        col = B[f]
        left = [i for i in idx if col[i] <= b]
        right = [i for i in idx if col[i] > b]
        return (f, self.cuts[f][b], self._grow(B, y, left, d + 1, nf),
                self._grow(B, y, right, d + 1, nf))

    def predict(self, x):
        s = 0.0
        for t in self.trees:
            while isinstance(t, tuple):
                t = t[2] if x[t[0]] < t[1] else t[3]
            s += t
        return s / len(self.trees)

    def importance(self, names, top=15):
        cnt = {}
        def walk(t, w):
            if isinstance(t, tuple):
                cnt[t[0]] = cnt.get(t[0], 0) + w
                walk(t[2], w / 2); walk(t[3], w / 2)
        for t in self.trees:
            walk(t, 1.0)
        tot = sum(cnt.values()) or 1
        return sorted(((names[f], v / tot) for f, v in cnt.items()), key=lambda p: -p[1])[:top]
