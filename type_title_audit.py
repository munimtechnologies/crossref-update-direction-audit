# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update-type audit 4: retractions and withdrawals typed as something else.

Crossref records a retraction or withdrawal as an `update-to` relation on the notice, with an
update type. Tools that ask "is this paper retracted?" read that type: retraction,
partial_retraction, withdrawal or removal. If a publisher deposits its "Withdrawn: ..." or
"Retraction notice" with the type addendum, correction or erratum, the paper looks merely
corrected. If Retraction Watch (whose data Crossref also serves, source "retraction-watch")
has no entry either, nothing in Crossref's update metadata says the paper was retracted.

This script walks every Crossref record that carries `update-to` (filter is-update:true) and:

1. flags publisher-deposited relations whose record title reads as a retraction or withdrawal
   notice while the relation's type is not retractive ("mistyped");
2. calls such a pair HIDDEN when no relation of a retractive type, from any source, targets
   either end of the pair anywhere in Crossref;
3. counts the opposite error: retractive-typed publisher relations whose record title reads as
   a correction, erratum, corrigendum or addendum and never mentions retraction ("overflag").

Definitions and predictions are fixed in PREREG-4.md. No API keys; api.crossref.org only.

Usage: python type_title_audit.py --out-dir /out [--max-pages N]
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

MAILTO = "mv2@munimtech.com"
UA = "crossref-type-title-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
API = "https://api.crossref.org/works"
SELECT = "DOI,update-to,title,type,publisher,member,created,container-title"
TARGET_SELECT = "DOI,title,type,member,publisher,created"
TARGET_BATCH = 60
GRADE_N = 30
TARGET_CAP = 20000
IWA_MEMBER = "945"

RETRACTIVE = {"retraction", "partial_retraction", "withdrawal", "removal"}

DASHES = "‐‑‒–—―−"
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}

_KEY = r"(?:retractions|retraction|retracted|withdrawn|withdrawal)"
_NEXT = (r"(?:$|\s*[:.\-\])(,;]|\s+(?:note|notes|notice|notices|statement|of|to|for|and|"
         r"article|paper|publication|letter)\b)")
# keyword at the start ("Retraction note to: ...", "Withdrawn: ...", "Notice of Retraction ...")
START = re.compile(r"^(?:notice of (?:retraction|withdrawal)\b|(?:partial |full )?" + _KEY + _NEXT + ")")
# keyword at the end after a separator ("...: Retraction", "... - RETRACTION", "...: [RETRACTED]")
END = re.compile(r"[:.\-\[(]\s*[\[(]?\s*(?:retraction notice|notice of retraction|" + _KEY + r")$")
CORRECTION_START = re.compile(
    r"^(?:author correction|publisher correction|correction|corrections|corrigendum|corrigenda|"
    r"erratum|errata|addendum|addenda|clarification)\b")
RETRACT_WORD = re.compile(r"retract|withdraw")
EOC = re.compile(r"expressions? of concern")


# ---------------------------------------------------------------- pure helpers
def clean_title(s):
    """Lower-case ASCII title with HTML removed and dashes kept as ' - '."""
    s = str(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    for ch in DASHES:
        s = s.replace(ch, " - ")
    for k, v in QUOTES.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def core_title(s):
    """clean_title without leading or trailing punctuation, quotes and brackets."""
    return clean_title(s).strip(" \"'[]().*:;,-")


def retraction_worded(title):
    """True if a title reads as a retraction or withdrawal notice (or a retracted-marked work)."""
    c = core_title(title)
    if not c:
        return False
    if CORRECTION_START.match(c) or EOC.search(c):
        return False
    return bool(START.match(c) or END.search(c))


def correction_worded(title):
    """True if a title reads as a correction-type notice and never mentions retraction."""
    c = core_title(title)
    if not c or RETRACT_WORD.search(c) or EOC.search(c):
        return False
    return bool(CORRECTION_START.match(c))


def norm_doi(d):
    return str(d or "").strip().lower()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def is_retractive(t):
    t = norm_type(t)
    return t in RETRACTIVE or t.startswith("retra") or "withdraw" in t


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def created_year(item):
    dp = ((item or {}).get("created") or {}).get("date-parts") or [[None]]
    try:
        return int(dp[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def relations_of(item):
    """One dict per update-to entry of a Crossref record."""
    r = norm_doi(item.get("DOI"))
    title = first(item.get("title"))
    rows = []
    for u in item.get("update-to") or []:
        if not isinstance(u, dict):
            continue
        rows.append({
            "record": r, "target": norm_doi(u.get("DOI")), "utype": norm_type(u.get("type")),
            "source": str(u.get("source") or ""), "member": str(item.get("member") or ""),
            "publisher": str(item.get("publisher") or ""), "year": created_year(item),
            "title": title, "container": first(item.get("container-title")),
        })
    return rows


def classify(rel):
    """'mistyped', 'overflag' or '' for one relation (publisher-deposited only)."""
    if rel["source"] != "publisher":
        return ""
    retr = is_retractive(rel["utype"])
    if not retr and retraction_worded(rel["title"]):
        return "mistyped"
    if retr and correction_worded(rel["title"]):
        return "overflag"
    return ""


def pair_visible(rel, retractive_targets):
    """True if any retractive relation (any source) targets either end of the pair."""
    return rel["record"] in retractive_targets or rel["target"] in retractive_targets


def pair_key(rel):
    return tuple(sorted((rel["record"], rel["target"])))


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return (num / den) if den else None


def compute_predictions(s):
    """Mechanical predictions fixed in PREREG-4.md (P8 is hand-graded)."""
    def holds(c):
        return None if c is None else bool(c)

    gate = s["complete"] and s["n_records"] >= 450000
    p3 = None
    if s["n_mistyped"] >= 20:
        p3 = s["n_mistyped_rw"] / s["n_mistyped"] >= 0.40
    p4 = (s["iwa_withdrawn_addendum"] >= 15 and s["iwa_withdrawal_typed"] == 0
          and s["iwa_withdrawn_pairs"] > 0
          and s["iwa_withdrawn_hidden"] == s["iwa_withdrawn_pairs"])
    p6 = None
    if s["recent_n"] >= 20 and s["old_n"] >= 20:
        r_new, r_old = s["recent_hidden"] / s["recent_n"], s["old_hidden"] / s["old_n"]
        p6 = (r_new >= 1.5 * r_old) if r_old > 0 else (r_new > 0)
    p7 = (s["n_overflag"] >= 30
          and s["n_overflag_unsupported"] / s["n_overflag"] >= 0.5)
    return {
        "G": holds(gate),
        "P1": holds(s["n_mistyped"] >= 200),
        "P2": holds(s["n_hidden_pairs"] >= 60),
        "P3": holds(p3),
        "P4": holds(p4),
        "P5": holds(s["hidden_members"] >= 12),
        "P6": holds(p6),
        "P7": holds(p7),
        "P8": "hand-graded (grade_hidden30.csv)",
    }


class Walker:
    """Keeps the flagged relations and the few totals the audit needs (not every relation)."""

    def __init__(self):
        self.flagged = []
        self.retr_any, self.retr_rw, self.retr_pub = set(), set(), set()
        self.rw_nonretr_records = set()
        self.utypes = collections.Counter()
        self.iwa_withdrawal_typed = 0
        self.n_records = 0
        self.n_relations = 0

    def add(self, item):
        """Process one Crossref record; returns True if any of its relations is flagged."""
        self.n_records += 1
        hit = False
        for rel in relations_of(item):
            self.n_relations += 1
            self.utypes[rel["utype"]] += 1
            if is_retractive(rel["utype"]) and rel["target"]:
                self.retr_any.add(rel["target"])
                if rel["source"] == "retraction-watch":
                    self.retr_rw.add(rel["target"])
                else:
                    self.retr_pub.add(rel["target"])
            elif rel["source"] == "retraction-watch":
                self.rw_nonretr_records.add(rel["record"])
            if rel["member"] == IWA_MEMBER and rel["utype"] == "withdrawal":
                self.iwa_withdrawal_typed += 1
            rel["class"] = classify(rel)
            if rel["class"]:
                rel["title"] = rel["title"][:200]
                rel["container"] = rel["container"][:80]
                self.flagged.append(rel)
                hit = True
        return hit

    def finish(self):
        """Mark visibility on every flagged relation (needs the complete walk)."""
        for r in self.flagged:
            r["self"] = r["record"] == r["target"]
            r["visible"] = pair_visible(r, self.retr_any)
            r["visible_rw"] = pair_visible(r, self.retr_rw)
            r["visible_publisher"] = pair_visible(r, self.retr_pub)
        return self.flagged


def tally(flagged, w, complete, total):
    """The statistics for the predictions, from flagged relations and walker totals."""
    mistyped = [r for r in flagged if r["class"] == "mistyped"]
    overflag = [r for r in flagged if r["class"] == "overflag"]
    hidden = [r for r in mistyped if not r["visible"]]
    iwa_wd = [r for r in mistyped if r["member"] == IWA_MEMBER
              and core_title(r["title"]).startswith("withdrawn")]
    recent = [r for r in mistyped if r["year"] is not None and r["year"] >= 2023]
    old = [r for r in mistyped if r["year"] is not None and r["year"] < 2020]
    return {
        "complete": complete, "n_records": w.n_records, "total_results": total,
        "relations": w.n_relations,
        "n_mistyped": len(mistyped),
        "n_mistyped_rw": sum(1 for r in mistyped if r["visible_rw"]),
        "n_mistyped_visible": sum(1 for r in mistyped if r["visible"]),
        "n_hidden_relations": len(hidden),
        "n_hidden_pairs": len({pair_key(r) for r in hidden}),
        "hidden_members": len({r["member"] for r in hidden}),
        "iwa_withdrawn_addendum": sum(1 for r in iwa_wd if r["utype"] == "addendum"),
        "iwa_withdrawal_typed": w.iwa_withdrawal_typed,
        "iwa_withdrawn_pairs": len({pair_key(r) for r in iwa_wd}),
        "iwa_withdrawn_hidden": len({pair_key(r) for r in iwa_wd if not r["visible"]}),
        "recent_n": len(recent), "recent_hidden": sum(1 for r in recent if not r["visible"]),
        "old_n": len(old), "old_hidden": sum(1 for r in old if not r["visible"]),
        "n_overflag": len(overflag),
        "n_overflag_unsupported": sum(1 for r in overflag if not r["visible_rw"]),
    }


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = [0.0]


def http_get(url, tries=6, timeout=120, gap=0.5):
    """(status, body); 400/404/410 are final; -1 = network failure. At most 2 requests/s."""
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST[0] + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[0] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["http_%d" % r.status] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["http_%d" % e.code] += 1
            if e.code in (400, 404, 410):
                return e.code, b""
            time.sleep(delay)
            delay = min(delay * 2, 120)
        except Exception:
            STATS["http_neterr"] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def walk(w, max_pages, raw_path):
    complete, total, cursor = False, None, "*"
    with gzip.open(raw_path, "wt", encoding="utf-8") as raw:
        for page in range(max_pages):
            url = ("%s?filter=is-update:true&rows=1000&select=%s&mailto=%s&cursor=%s"
                   % (API, SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
            st, body = http_get(url)
            if st != 200:
                print("page %d failed: %s" % (page, st), file=sys.stderr, flush=True)
                break
            try:
                msg = json.loads(body.decode("utf-8")).get("message") or {}
            except ValueError:
                print("page %d: bad JSON" % page, file=sys.stderr, flush=True)
                break
            total = msg.get("total-results", total)
            items = msg.get("items") or []
            if not items:
                complete = True
                break
            for it in items:
                if w.add(it):
                    raw.write(json.dumps(it, ensure_ascii=False) + "\n")
            cursor = msg.get("next-cursor") or ""
            if not cursor:
                complete = True
                break
            if page % 25 == 0:
                print("records %d after page %d (total %s)" % (w.n_records, page + 1, total),
                      flush=True)
    return complete, total


def lookup_targets(dois):
    """{doi: {title, type, member, publisher}} for the DOIs Crossref returns."""
    out = {}
    clean = [d for d in dois if d and "," not in d and not re.search(r"\s", d)]
    for i in range(0, len(clean), TARGET_BATCH):
        b = clean[i:i + TARGET_BATCH]
        f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in b)
        st, body = http_get("%s?filter=%s&rows=%d&select=%s&mailto=%s"
                            % (API, f, len(b) + 5, TARGET_SELECT, MAILTO))
        if st != 200:
            continue
        try:
            items = (json.loads(body.decode("utf-8")).get("message") or {}).get("items") or []
        except ValueError:
            continue
        for it in items:
            out[norm_doi(it.get("DOI"))] = {
                "title": first(it.get("title"))[:200], "type": str(it.get("type") or ""),
                "member": str(it.get("member") or ""), "publisher": str(it.get("publisher") or "")}
    return out


# ---------------------------------------------------------------- main
FIELDS = ["record", "target", "self", "utype", "source", "member", "publisher", "year",
          "container", "title", "visible", "visible_rw", "visible_publisher", "t_title",
          "t_type", "t_member", "t_retraction_worded"]


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=1500)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    w = Walker()
    complete, total = walk(w, a.max_pages, os.path.join(a.out_dir, "flagged_records_raw.jsonl.gz"))
    flagged = w.finish()
    print("records %d (total %s), relations %d, flagged %d, complete=%s"
          % (w.n_records, total, w.n_relations, len(flagged), complete), flush=True)

    mistyped = [r for r in flagged if r["class"] == "mistyped"]
    overflag = [r for r in flagged if r["class"] == "overflag"]
    hidden = [r for r in mistyped if not r["visible"]]

    need = sorted({r["target"] for r in hidden + overflag if not r["self"]})[:TARGET_CAP]
    tmeta = lookup_targets(need)
    for r in flagged:
        m = tmeta.get(r["target"])
        if m:
            r["t_title"], r["t_type"], r["t_member"] = m["title"], m["type"], m["member"]
            r["t_retraction_worded"] = retraction_worded(m["title"])

    def by_pub(r):
        return (r["publisher"], r["record"], r["target"])

    write_csv(os.path.join(a.out_dir, "mistyped.csv"), sorted(mistyped, key=by_pub), FIELDS)
    write_csv(os.path.join(a.out_dir, "hidden.csv"), sorted(hidden, key=by_pub), FIELDS)
    write_csv(os.path.join(a.out_dir, "overflag.csv"), sorted(overflag, key=by_pub), FIELDS)
    seen, grade = set(), []
    for r in sorted(hidden, key=lambda r: sha_key("g4", r["record"], r["target"])):
        if pair_key(r) in seen:
            continue
        seen.add(pair_key(r))
        grade.append(r)
        if len(grade) >= GRADE_N:
            break
    write_csv(os.path.join(a.out_dir, "grade_hidden30.csv"), grade, FIELDS + ["grade", "note"])

    per = collections.defaultdict(collections.Counter)
    for r in mistyped:
        k = (r["member"], r["publisher"])
        per[k]["mistyped"] += 1
        per[k]["hidden"] += 0 if r["visible"] else 1
    for r in overflag:
        per[(r["member"], r["publisher"])]["overflag"] += 1
    mrows = [{"member": k[0], "publisher": k[1], "mistyped": c["mistyped"], "hidden": c["hidden"],
              "overflag": c["overflag"]} for k, c in per.items()]
    mrows.sort(key=lambda x: (-x["hidden"], -x["mistyped"], -x["overflag"]))
    write_csv(os.path.join(a.out_dir, "member_table.csv"), mrows,
              ["member", "publisher", "mistyped", "hidden", "overflag"])

    s = tally(flagged, w, complete, total)
    mistyped_records = {r["record"] for r in mistyped}
    summary = dict(s)
    summary.update({
        "mistyped_by_utype": dict(collections.Counter(r["utype"] for r in mistyped).most_common()),
        "hidden_by_utype": dict(collections.Counter(r["utype"] for r in hidden).most_common()),
        "hidden_self": sum(1 for r in hidden if r["self"]),
        "hidden_by_publisher": collections.Counter(r["publisher"] for r in hidden).most_common(30),
        "hidden_by_year": dict(sorted(collections.Counter(r["year"] for r in hidden
                                                          if r["year"]).items())),
        "hidden_target_title_marked": sum(1 for r in hidden if r.get("t_retraction_worded")),
        "hidden_targets_looked_up": sum(1 for r in hidden if r.get("t_title") is not None),
        "overflag_by_utype": dict(collections.Counter(r["utype"] for r in overflag).most_common()),
        "overflag_by_publisher": collections.Counter(r["publisher"] for r in overflag).most_common(30),
        "rw_nonretractive_on_mistyped_records": len(w.rw_nonretr_records & mistyped_records),
        "rate_recent_hidden": share(s["recent_hidden"], s["recent_n"]),
        "rate_old_hidden": share(s["old_hidden"], s["old_n"]),
        "utypes_all": dict(w.utypes.most_common(40)),
        "targets_looked_up": len(tmeta), "targets_needed": len(need),
    })
    summary["predictions"] = compute_predictions(s)
    summary["http"] = dict(STATS)
    summary["elapsed_s"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: summary[k] for k in ("n_records", "n_mistyped", "n_hidden_pairs",
                                              "n_overflag", "predictions")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
