"""Logistic regression trained by SGD (pure Python) + metrics (AUC, PR-AUC, F1)."""
import math
import random


class Logistic:
    def __init__(self, n, lr=0.05, epochs=12, l2=1e-4, pos_weight=3.0, seed=1):
        self.w, self.b = [0.0] * n, 0.0
        self.lr, self.epochs, self.l2, self.pw = lr, epochs, l2, pos_weight
        self.rnd = random.Random(seed)
        self.mu, self.sd = [0.0] * n, [1.0] * n

    def _z(self, x):
        return [(v - m) / s for v, m, s in zip(x, self.mu, self.sd)]

    def fit(self, X, y):
        n, m = len(X[0]), len(X)
        self.mu = [sum(r[i] for r in X) / m for i in range(n)]
        self.sd = [max(math.sqrt(sum((r[i] - self.mu[i]) ** 2 for r in X) / m), 1e-9)
                   for i in range(n)]
        Z = [self._z(r) for r in X]
        idx = list(range(m))
        for _ in range(self.epochs):
            self.rnd.shuffle(idx)
            for i in idx:
                p = self._p(Z[i])
                g = (p - y[i]) * (self.pw if y[i] else 1.0)
                for j in range(n):
                    self.w[j] -= self.lr * (g * Z[i][j] + self.l2 * self.w[j])
                self.b -= self.lr * g
        return self

    def _p(self, z):
        t = sum(w * v for w, v in zip(self.w, z)) + self.b
        t = max(min(t, 30), -30)
        return 1 / (1 + math.exp(-t))

    def predict(self, x):
        return self._p(self._z(x))

    def weights(self, names):
        return sorted(zip(names, self.w), key=lambda p: -abs(p[1]))


def auc(scores, y):
    pairs = sorted(zip(scores, y))
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return float("nan")
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(1 for k in range(i, j) if pairs[k][1])
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def pr_auc(scores, y):
    pairs = sorted(zip(scores, y), reverse=True)
    pos = sum(y)
    tp = fp = 0
    prev_r, area = 0.0, 0.0
    for s, t in pairs:
        tp += t
        fp += 1 - t
        r = tp / pos
        p = tp / (tp + fp)
        area += (r - prev_r) * p
        prev_r = r
    return area


def prf(scores, y, thr):
    tp = sum(1 for s, t in zip(scores, y) if s >= thr and t)
    fp = sum(1 for s, t in zip(scores, y) if s >= thr and not t)
    fn = sum(1 for s, t in zip(scores, y) if s < thr and t)
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return p, r, (2 * p * r / (p + r) if p + r else 0)


def best_threshold(scores, y):
    best = (0, 0.5)
    for q in range(5, 100, 2):
        thr = sorted(scores)[int(len(scores) * q / 100)]
        f1 = prf(scores, y, thr)[2]
        if f1 > best[0]:
            best = (f1, thr)
    return best[1]
