"""Graph analytics on the transaction graph. Edge a->b means money flowed from tx a into tx b."""
from collections import defaultdict


class Graph:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.out = defaultdict(list)
        self.inn = defaultdict(list)
        for a, b in edges:
            self.out[a].append(b)
            self.inn[b].append(a)

    def indeg(self, n):
        return len(self.inn[n])

    def outdeg(self, n):
        return len(self.out[n])


def relay_chains(g):
    """Layering chains: runs of transactions that each take exactly one input and give one output.
    Returns {node: (chain_length, position_from_start)}.
    """
    def relay(n):
        return len(g.inn[n]) == 1 and len(g.out[n]) == 1

    res = {}
    seen = set()
    for n in g.nodes:
        if n in seen or not relay(n):
            continue
        # walk back to the start of the run
        start = n
        guard = 0
        while relay(g.inn[start][0]) and g.inn[start][0] not in seen and guard < 5000:
            start = g.inn[start][0]
            guard += 1
        chain, cur = [], start
        while relay(cur) and cur not in seen:
            seen.add(cur)
            chain.append(cur)
            cur = g.out[cur][0]
        for i, c in enumerate(chain):
            res[c] = (len(chain), i)
    return res


def pagerank(g, iters=15, d=0.85, reverse=False):
    n = len(g.nodes)
    pr = {v: 1.0 / n for v in g.nodes}
    nxt_of = g.inn if reverse else g.out
    prv_of = g.out if reverse else g.inn
    for _ in range(iters):
        new = {v: (1 - d) / n for v in g.nodes}
        dangling = sum(pr[v] for v in g.nodes if not nxt_of[v])
        for v in g.nodes:
            outs = nxt_of[v]
            if outs:
                share = d * pr[v] / len(outs)
                for w in outs:
                    new[w] += share
        add = d * dangling / n
        pr = {v: new[v] + add for v in g.nodes}
    return pr


def taint(g, seeds, hops=3, decay=0.5):
    """Propagate suspicion from known-bad transactions in both directions along the flow.
    Returns (downstream, upstream): how much illicit flow reaches / feeds each node.
    """
    down = defaultdict(float)
    up = defaultdict(float)
    for direction, store in ((g.out, down), (g.inn, up)):
        frontier = {s: 1.0 for s in seeds}
        for _ in range(hops):
            nxt = defaultdict(float)
            for v, w in frontier.items():
                nbrs = direction[v]
                if not nbrs:
                    continue
                share = decay * w / len(nbrs)
                for u in nbrs:
                    nxt[u] += share
            for u, w in nxt.items():
                store[u] += w
            frontier = nxt
    return down, up


def neighbour_counts(g, label_known):
    """For each node: how many direct neighbours are known illicit / known licit."""
    ill, lic = defaultdict(int), defaultdict(int)
    for v in g.nodes:
        for u in g.out[v] + g.inn[v]:
            k = label_known.get(u)
            if k == 1:
                ill[v] += 1
            elif k == 0:
                lic[v] += 1
    return ill, lic


def two_hop(g):
    """Fan-in / fan-out reach within 2 hops (hub detection)."""
    fin, fout = {}, {}
    for v in g.nodes:
        s = set()
        for u in g.inn[v]:
            s.update(g.inn[u])
        fin[v] = len(s)
        t = set()
        for u in g.out[v]:
            t.update(g.out[u])
        fout[v] = len(t)
    return fin, fout
