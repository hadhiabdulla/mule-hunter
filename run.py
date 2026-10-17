"""Mule Hunter command line.

  python run.py --download      fetch the real Elliptic dataset (about 700 MB, one time)
  python run.py --elliptic      train + evaluate on Elliptic, write results/
  python run.py --serve         open the web app (Elliptic results, CSV upload, live mode)
  python run.py --csv my.csv    score your own transactions file from the terminal
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--elliptic", action="store_true")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--csv")
    ap.add_argument("--live", action="store_true", help="score recent real Bitcoin transactions")
    a = ap.parse_args()
    if not any([a.download, a.elliptic, a.serve, a.csv, a.live]):
        ap.print_help()
        return
    if a.download:
        from mulehunter import data
        data.download()
        print("Dataset ready.")
    if a.elliptic:
        from mulehunter import data, pipeline, export
        nodes, edges, label, step = data.load()
        res = pipeline.run(nodes, edges, label, step, data.load_features(nodes))
        export.export(res, label, step)
        print(open(export.RESULTS + "/metrics.md").read())
        print("Written to results/. Open the web app with: python run.py --serve")
    if a.csv:
        from mulehunter import upload, accounts
        tx, rep = upload.parse(open(a.csv, newline="", encoding="utf-8-sig").read())
        print(f"Read {rep['rows_ok']} rows ({rep['rows_skipped']} skipped).")
        res = accounts.analyse(tx)
        for r in sorted(res["accounts"].values(), key=lambda r: -r["risk"])[:15]:
            print(f"{r['account']:<24} risk {r['risk']:>5}  " + "; ".join(x["text"] for x in r["reasons"][:2]))
    if a.live:
        from mulehunter import live, accounts
        edges, info = live.fetch()
        res = accounts.analyse(edges)
        print(info)
        for r in sorted(res["accounts"].values(), key=lambda r: -r["risk"])[:15]:
            print(f"{r['account'][:28]:<30} risk {r['risk']:>5}  " + "; ".join(x["text"] for x in r["reasons"][:2]))
    if a.serve:
        from mulehunter import web
        web.serve(a.port)


if __name__ == "__main__":
    sys.exit(main())
