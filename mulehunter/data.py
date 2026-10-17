"""Download and load the real Elliptic Bitcoin transaction graph (not redistributed here)."""
import csv
import os
from array import array
import sys
import urllib.request

BASE = "https://huggingface.co/datasets/yhoma/elliptic-bitcoin-dataset/resolve/main/"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _get(url, dest):
    print(f"  downloading {os.path.basename(dest)} ...", flush=True)
    urllib.request.urlretrieve(url, dest)


def download(data_dir=DATA):
    """Fetch labels + edges, then stream the 690 MB feature file keeping only (tx, time step)."""
    os.makedirs(data_dir, exist_ok=True)
    for name, local in (("elliptic_txs_classes.csv", "classes.csv"),
                        ("elliptic_txs_edgelist.csv", "edgelist.csv")):
        p = os.path.join(data_dir, local)
        if not os.path.exists(p):
            _get(BASE + name, p)
    ts = os.path.join(data_dir, "timesteps.csv")
    fb = os.path.join(data_dir, "features.bin")
    if not (os.path.exists(ts) and os.path.exists(fb)):
        print("  streaming features file (690 MB) into a compact local cache ...", flush=True)
        n = 0
        buf = array("f")
        with urllib.request.urlopen(BASE + "elliptic_txs_features.csv") as r, \
                open(ts + ".part", "w") as out:
            out.write("txId,time_step\n")
            for line in r:
                parts = line.decode().rstrip().split(",")
                out.write(f"{parts[0]},{parts[1]}\n")
                buf.extend(float(v) for v in parts[2:])
                n += 1
                if n % 50000 == 0:
                    print(f"    {n} rows", flush=True)
        with open(fb + ".part", "wb") as f:
            buf.tofile(f)
        os.replace(fb + ".part", fb)
        os.replace(ts + ".part", ts)
    return data_dir


def load(data_dir=DATA):
    """Returns (nodes, edges, label, step). label: 1 illicit, 0 licit, None unknown."""
    for f in ("classes.csv", "edgelist.csv", "timesteps.csv", "features.bin"):
        if not os.path.exists(os.path.join(data_dir, f)):
            sys.exit("Dataset missing. Run:  python run.py --download")
    label, step = {}, {}
    with open(os.path.join(data_dir, "classes.csv")) as f:
        for r in csv.DictReader(f):
            label[r["txId"]] = {"1": 1, "2": 0}.get(r["class"])
    with open(os.path.join(data_dir, "timesteps.csv")) as f:
        for r in csv.DictReader(f):
            step[r["txId"]] = int(r["time_step"])
    edges = []
    with open(os.path.join(data_dir, "edgelist.csv")) as f:
        next(f)
        for line in f:
            a, b = line.strip().split(",")
            edges.append((a, b))
    return list(label), edges, label, step


N_FEATURES = 165    # 93 local + 72 aggregated (anonymised by Elliptic)


def load_features(nodes_in_order, data_dir=DATA):
    """Returns {tx: list of 165 floats} lazily as a function (keeps memory low)."""
    buf = array("f")
    with open(os.path.join(data_dir, "features.bin"), "rb") as f:
        buf.fromfile(f, os.path.getsize(os.path.join(data_dir, "features.bin")) // 4)
    index = {n: i for i, n in enumerate(nodes_in_order)}
    return lambda n: buf[index[n] * N_FEATURES:(index[n] + 1) * N_FEATURES].tolist()
