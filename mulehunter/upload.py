"""Parse a user-supplied transaction CSV: column auto-detection, mapping, validation."""
import csv
import io
from datetime import datetime

ROLES = ["sender", "receiver", "amount", "timestamp", "label"]
HINTS = {
    "sender": ["sender", "src", "source", "from", "payer", "origin", "orig", "nameorig", "debit"],
    "receiver": ["receiver", "dst", "dest", "destination", "to", "payee", "beneficiary", "namedest", "credit"],
    "amount": ["amount", "amt", "value", "sum"],
    "timestamp": ["timestamp", "time", "date", "datetime", "created", "ts"],
    "label": ["label", "is_fraud", "isfraud", "fraud", "is_mule", "mule", "illicit", "flag"],
}
FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M",
           "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%m/%d/%Y %H:%M",
           "%m/%d/%Y"]
MAX_ROWS = 200_000


def read_header(text):
    rows = csv.reader(io.StringIO(text))
    header = next(rows, [])
    sample = [r for _, r in zip(range(5), rows)]
    return [h.strip() for h in header], sample


def guess_mapping(header):
    low = [h.lower().replace(" ", "_") for h in header]
    m = {}
    for role, hints in HINTS.items():
        for h in hints:
            for i, c in enumerate(low):
                if c == h and i not in m.values():
                    m[role] = i
                    break
            if role in m:
                break
        if role not in m:
            for h in hints:
                for i, c in enumerate(low):
                    if h in c and i not in m.values():
                        m[role] = i
                        break
                if role in m:
                    break
    return m


def parse_ts(v):
    v = v.strip()
    if v.replace(".", "", 1).isdigit():
        x = float(v)
        if x > 1e11:
            x /= 1000
        if x > 1e8:
            return datetime.utcfromtimestamp(x)
    for f in FORMATS:
        try:
            return datetime.strptime(v, f)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(v.replace("Z", ""))
    except ValueError:
        raise ValueError("unrecognised date")


def parse(text, mapping=None):
    """Returns (transactions, report). report has row counts and the first problems found."""
    rows = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(rows, [])]
    if not header:
        raise ValueError("The file is empty.")
    mapping = {k: int(v) for k, v in (mapping or guess_mapping(header)).items() if v not in ("", None)}
    missing = [r for r in ("sender", "receiver", "amount", "timestamp") if r not in mapping]
    if missing:
        raise ValueError("Could not find columns for: " + ", ".join(missing) +
                         ". Choose them in the mapping step.")
    tx, problems, bad = [], [], 0
    for n, r in enumerate(rows, start=2):
        if not r:
            continue
        if n - 1 > MAX_ROWS:
            problems.append(f"Stopped at {MAX_ROWS} rows (limit for the local demo).")
            break
        try:
            src, dst = r[mapping["sender"]].strip(), r[mapping["receiver"]].strip()
            if not src or not dst:
                raise ValueError("empty sender or receiver")
            if src == dst:
                raise ValueError("sender equals receiver")
            amt = float(r[mapping["amount"]].replace(",", ""))
            if amt <= 0:
                raise ValueError("amount must be positive")
            ts = parse_ts(r[mapping["timestamp"]])
            lab = None
            if "label" in mapping and r[mapping["label"]].strip() != "":
                v = r[mapping["label"]].strip().lower()
                lab = 1 if v in ("1", "true", "yes", "y", "fraud", "mule", "illicit") else 0
            tx.append({"src": src, "dst": dst, "amount": amt, "ts": ts, "label": lab})
        except (ValueError, IndexError) as e:
            bad += 1
            if len(problems) < 8:
                problems.append(f"Row {n}: {e}")
    if len(tx) < 10:
        raise ValueError("Fewer than 10 valid rows. " + " ".join(problems[:3]))
    return tx, {"rows_ok": len(tx), "rows_skipped": bad, "problems": problems,
                "mapping": {k: header[v] for k, v in mapping.items()},
                "has_labels": any(t["label"] is not None for t in tx)}
