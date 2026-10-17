"""Public lists of known-bad crypto addresses, fetched when needed (nothing is stored in the repo).

- OFAC sanctions list (US Treasury), extracted nightly by the 0xB10C project (MIT)
- ScamSniffer scam-database, Ethereum phishing addresses (GPL-3.0, so fetched, never bundled)
Only the lists are downloaded. No account or transaction data is ever sent anywhere.
"""
import json
import time
import urllib.request

OFAC_URLS = [
    "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_XBT.txt",
    "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_ETH.txt",
    "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists/sanctioned_addresses_TRX.txt",
]
SCAM_URL = "https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json"
_cache = {"at": 0, "data": None}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mule-hunter/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()


def load(max_age=3600):
    """Returns {"ofac": set, "scam": set, "errors": [..]}. Cached for an hour."""
    if _cache["data"] and time.time() - _cache["at"] < max_age:
        return _cache["data"]
    ofac, scam, errors = set(), set(), []
    for u in OFAC_URLS:
        try:
            ofac.update(a.strip().lower() for a in _get(u).split() if a.strip())
        except Exception as e:
            errors.append(f"OFAC list: {e}")
    try:
        scam.update(a.lower() for a in json.loads(_get(SCAM_URL)))
    except Exception as e:
        errors.append(f"ScamSniffer list: {e}")
    data = {"ofac": ofac, "scam": scam, "errors": errors}
    if ofac or scam:
        _cache.update(at=time.time(), data=data)
    return data


def apply(res, lists=None):
    """Mark accounts that appear on a list. Returns a small summary for the UI."""
    lists = lists or load()
    hits = {"ofac": 0, "scam": 0}
    for a, r in res["accounts"].items():
        key = a.lower()
        if key in lists["ofac"]:
            r["risk"] = 100.0
            r["reasons"].insert(0, {"signal": "ofac", "strength": 1.0,
                                    "text": "On the US OFAC sanctions list (confirmed, not a guess)"})
            hits["ofac"] += 1
        elif key in lists["scam"]:
            r["risk"] = max(r["risk"], 90.0)
            r["reasons"].insert(0, {"signal": "scam", "strength": 1.0,
                                    "text": "On the ScamSniffer list of reported scam addresses"})
            hits["scam"] += 1
    return {"ofac_loaded": len(lists["ofac"]), "scam_loaded": len(lists["scam"]),
            "ofac_hits": hits["ofac"], "scam_hits": hits["scam"], "errors": lists["errors"]}
