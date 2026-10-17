"""Turn the Elliptic pipeline output into JSON for the web UI plus markdown case files."""
import json
import os

from . import pipeline as P

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def export(res, label, step, out_dir=RESULTS):
    os.makedirs(os.path.join(out_dir, "cases"), exist_ok=True)
    final, g = res["final"], res["g"]
    cl = P.clusters(res, label)
    show = cl[:8]
    keep = {n for c in show for n in c["nodes"]}
    nodes = [{"id": n, "risk": round(100 * final[n], 1),
              "label": {1: "illicit", 0: "licit", None: "unknown"}[label[n]],
              "step": step[n], "reasons": P.explain(res, n)} for n in keep]
    edges = [{"s": n, "d": m} for n in keep for m in g.out[n] if m in keep]
    leads = sorted((n for n in res["test"] if label[n] is None), key=lambda n: -final[n])[:50]
    confirmed = sorted((n for n in res["test"] if label[n] == 1), key=lambda n: -final[n])[:25]
    row = lambda n: {"id": n, "risk": round(100 * final[n], 1), "step": step[n],
                     "label": {1: "illicit", 0: "licit", None: "unknown"}[label[n]],
                     "reasons": P.explain(res, n)}
    data = {
        "metrics": res["metrics"], "importance": [[a, round(b, 4)] for a, b in res["weights"]],
        "clusters": [{k: v for k, v in c.items() if k != "nodes"} | {"members": c["nodes"][:40]}
                     for c in show],
        "network": {"nodes": nodes, "edges": edges},
        "leads": [row(n) for n in leads], "confirmed": [row(n) for n in confirmed],
        "totals": {"transactions": len(res["g"].nodes), "test_transactions": len(res["test"]),
                   "high_risk": sum(1 for n in res["test"] if final[n] >= 0.5)},
    }
    with open(os.path.join(out_dir, "elliptic.json"), "w") as f:
        json.dump(data, f)
    for c in show:
        with open(os.path.join(out_dir, "cases", f"case_{c['id']}.md"), "w") as f:
            f.write(case_file(c, res, label, step))
    with open(os.path.join(out_dir, "metrics.md"), "w") as f:
        f.write(metrics_md(res["metrics"]))
    return data


def case_file(c, res, label, step):
    final, g = res["final"], res["g"]
    ms = sorted(c["nodes"], key=lambda n: -final[n])
    steps = sorted({step[n] for n in ms})
    lines = [f"# Case {c['id']}: suspected laundering network", "",
             f"- Transactions in the network: {c['size']}",
             f"- Already labelled illicit in the dataset: {c['confirmed_illicit']}",
             f"- Unlabelled transactions the system flags as new leads: {c['unlabelled_leads']}",
             f"- Labelled licit (possible false alarms): {c['known_licit']}",
             f"- Time steps (about 2 weeks each): {steps[0]}-{steps[-1]}",
             f"- Average risk: {100 * c['avg_risk']:.0f}/100", "",
             "## Highest-risk transactions", ""]
    for n in ms[:8]:
        lines.append(f"### {n}  (risk {100 * final[n]:.0f}, {({1: 'illicit', 0: 'licit', None: 'unlabelled'})[label[n]]})")
        for r in P.explain(res, n):
            lines.append(f"- {r}")
        lines.append("")
    lines += ["## Recommended analyst actions", "",
              "- Review the unlabelled leads first; they sit inside a cluster that already contains confirmed illicit activity.",
              "- Trace the funds downstream from the highest-risk transaction to find the cash-out point.",
              "- Add confirmed findings back as seeds; the taint score will then widen to related transactions.", ""]
    return "\n".join(lines)


def metrics_md(m):
    sp = m["split"]
    out = ["# Evaluation on real Elliptic labels", "",
           f"Train steps {sp['train_steps']} ({sp['train_labelled']} labelled, {sp['train_illicit']} illicit). "
           f"Test steps {sp['test_steps']} ({sp['test_labelled_evaluated']} labelled, "
           f"{sp['test_illicit_evaluated']} illicit). {sp['analyst_seeds']} test-period illicit transactions "
           "were revealed as analyst seeds and are excluded from scoring.", "",
           "| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 | Precision@k |", "|---|---|---|---|---|---|---|"]
    for k, v in m.items():
        if k == "split":
            continue
        out.append(f"| {k} | {v['roc_auc']:.3f} | {v['pr_auc']:.3f} | {v['precision']:.3f} | "
                   f"{v['recall']:.3f} | {v['f1']:.3f} | {v['precision_at_k']:.3f} |")
    return "\n".join(out) + "\n"
