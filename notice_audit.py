# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update-type audit 4b: a post-hoc correction of audit 4 (NOT pre-registered).

Audit 4 called a mistyped relation (a notice titled as a retraction or withdrawal, deposited
with a non-retractive update type) "hidden" when no retractive relation targets either end of
the pair. Hand grading (GRADING-4.md) found that this misses one case: the notice record
itself can carry a second relation, often from Retraction Watch, that retracts the real
article. Example: 10.1016/j.bja.2018.11.005 points at itself as `erratum` (publisher) and at
10.1093/bja/74.3.293 as `retraction` (retraction-watch). The retraction is recorded; only the
publisher's own link is wrong.

This script walks the same population (filter is-update:true) with the same title rules as
audit 4 and judges each NOTICE as a whole:

- hidden: no mistyped target of the notice is retracted anywhere, and the notice record
  carries no retractive relation (any source) to any target;
- partly_hidden: some mistyped targets are retracted elsewhere, others are not, and the notice
  record carries no retractive relation;
- covered_on_notice: the notice record carries a retractive relation to some target;
- visible: every mistyped target (or the notice) is retracted elsewhere.

It also lists the overflag relations (retractive type on a correction-titled notice) that no
Retraction Watch relation supports, with their target titles, for hand grading: these are
candidate papers that Crossref shows as retracted although the notice reads as a correction.

No API keys; api.crossref.org only. Usage: python notice_audit.py --out-dir /out
"""
import argparse
import collections
import csv
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
UA = "crossref-notice-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
API = "https://api.crossref.org/works"
SELECT = "DOI,update-to,title,type,publisher,member,created,container-title"
TARGET_SELECT = "DOI,title,type,member,publisher,created"
TARGET_BATCH = 60
GRADE_N = 20

RETRACTIVE = {"retraction", "partial_retraction", "withdrawal", "removal"}
DASHES = "‐‑‒–—―−"
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}

_KEY = r"(?:retractions|retraction|retracted|withdrawn|withdrawal)"
_NEXT = (r"(?:$|\s*[:.\-\])(,;]|\s+(?:note|notes|notice|notices|statement|of|to|for|and|"
         r"article|paper|publication|letter)\b)")
START = re.compile(r"^(?:notice of (?:retraction|withdrawal)\b|(?:partial |full )?" + _KEY + _NEXT + ")")
END = re.compile(r"[:.\-\[(]\s*[\[(]?\s*(?:retraction notice|notice of retraction|" + _KEY + r")$")
CORRECTION_START = re.compile(
    r"^(?:author correction|publisher correction|correction|corrections|corrigendum|corrigenda|"
    r"erratum|errata|addendum|addenda|clarification)\b")
RETRACT_WORD = re.compile(r"retract|withdraw")
EOC = re.compile(r"expressions? of concern")

# the 30 notices already hand-graded in audit 4 (excluded from this run's grading sample)
AUDIT4_SAMPLE = {
    "10.1016/j.ijpx.2025.100388", "10.1177/0309524x18767745", "10.1177/0920203x19856121",
    "10.2166/ws.2024.152", "10.1016/j.jbc.2025.110619", "10.1007/s35144-015-0718-3",
    "10.1177/1758155919844912", "10.1016/j.eururo.2014.07.015", "10.1016/j.jamcollsurg.2017.04.030",
    "10.1016/j.phytochem.2008.11.009", "10.1016/j.scitotenv.2026.182102", "10.3352/jeehp.2024.21.41",
    "10.1016/j.bja.2018.11.005", "10.1177/02692163241243121", "10.1177/15366006241257805",
    "10.1016/j.ijhydene.2026.157750", "10.1177/10445498251371637", "10.1016/j.cplett.2026.142639",
    "10.1136/jisakos-2019-reviewers2018wit", "10.1016/j.neo.2023.100917", "10.1177/09718907221094431",
    "10.1177/17470161221125530", "10.29328/journal.ijpra.1001106", "10.2166/ws.2024.194",
    "10.1016/j.ijhydene.2026.158064", "10.1016/j.bja.2018.11.002", "10.1002/prep.202480142",
    "10.17352/amp.000151", "10.1061/jupddm.upeng-6523", "10.1016/s1526-5900(03)00777-6",
}


# ---------------------------------------------------------------- pure helpers (as audit 4)
def clean_title(s):
    s = str(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    for ch in DASHES:
        s = s.replace(ch, " - ")
    for k, v in QUOTES.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def core_title(s):
    return clean_title(s).strip(" \"'[]().*:;,-")


def retraction_worded(title):
    c = core_title(title)
    if not c:
        return False
    if CORRECTION_START.match(c) or EOC.search(c):
        return False
    return bool(START.match(c) or END.search(c))


def correction_worded(title):
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
    if rel["source"] != "publisher":
        return ""
    retr = is_retractive(rel["utype"])
    if not retr and retraction_worded(rel["title"]):
        return "mistyped"
    if retr and correction_worded(rel["title"]):
        return "overflag"
    return ""


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return (num / den) if den else None


# ---------------------------------------------------------------- walker and judgement
class Walker:
    def __init__(self):
        self.mistyped, self.overflag = [], []
        self.retr_any, self.retr_rw = set(), set()
        self.rec_retr_any, self.rec_retr_rw = set(), set()
        self.n_records = 0
        self.n_relations = 0

    def add(self, item):
        self.n_records += 1
        hit = False
        for rel in relations_of(item):
            self.n_relations += 1
            if is_retractive(rel["utype"]) and rel["target"]:
                self.retr_any.add(rel["target"])
                self.rec_retr_any.add(rel["record"])
                if rel["source"] == "retraction-watch":
                    self.retr_rw.add(rel["target"])
                    self.rec_retr_rw.add(rel["record"])
            c = classify(rel)
            if c:
                rel["class"] = c
                rel["title"] = rel["title"][:200]
                rel["container"] = rel["container"][:80]
                (self.mistyped if c == "mistyped" else self.overflag).append(rel)
                hit = True
        return hit

    def finish(self):
        for r in self.mistyped + self.overflag:
            r["self"] = r["record"] == r["target"]
            r["pair_hidden"] = (r["record"] not in self.retr_any
                                and r["target"] not in self.retr_any)
            r["notice_covered"] = r["record"] in self.rec_retr_any
            r["rw_either"] = r["record"] in self.retr_rw or r["target"] in self.retr_rw
        return self.mistyped, self.overflag


def notice_status(n_rel, n_pair_hidden, covered):
    if covered and n_pair_hidden > 0:
        return "covered_on_notice"
    if n_pair_hidden == 0:
        return "visible"
    if n_pair_hidden == n_rel:
        return "hidden"
    return "partly_hidden"


def notices_from(mistyped):
    """{record: dict} one entry per notice with at least one mistyped relation."""
    out = {}
    for r in mistyped:
        n = out.setdefault(r["record"], {
            "record": r["record"], "member": r["member"], "publisher": r["publisher"],
            "year": r["year"], "container": r["container"], "title": r["title"],
            "targets": [], "utypes": set(), "n_rel": 0, "n_pair_hidden": 0,
            "covered": r["notice_covered"], "self_only": True})
        if r["target"] in n["targets"]:
            continue
        n["targets"].append(r["target"])
        n["utypes"].add(r["utype"])
        n["n_rel"] += 1
        n["n_pair_hidden"] += 1 if r["pair_hidden"] else 0
        n["self_only"] = n["self_only"] and r["self"]
    for n in out.values():
        n["status"] = notice_status(n["n_rel"], n["n_pair_hidden"], n["covered"])
    return out


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = [0.0]


def http_get(url, tries=6, timeout=120, gap=0.5):
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


def walk(w, max_pages):
    complete, total, cursor = False, None, "*"
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
            w.add(it)
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            complete = True
            break
        if page % 50 == 0:
            print("records %d after page %d (total %s)" % (w.n_records, page + 1, total), flush=True)
    return complete, total


def lookup_targets(dois):
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
                "title": first(it.get("title"))[:160], "type": str(it.get("type") or ""),
                "member": str(it.get("member") or "")}
    return out


# ---------------------------------------------------------------- main
def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


NOTICE_FIELDS = ["record", "status", "member", "publisher", "year", "container", "title",
                 "utypes", "n_targets", "n_pair_hidden", "self_only", "targets",
                 "target_titles", "any_target_marked"]
OVER_FIELDS = ["record", "target", "self", "utype", "member", "publisher", "year", "container",
               "title", "rw_either", "t_title", "t_type", "t_marked", "grade", "note"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=1500)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    w = Walker()
    complete, total = walk(w, a.max_pages)
    mistyped, overflag = w.finish()
    notices = notices_from(mistyped)
    print("records %d (total %s), mistyped %d, notices %d, complete=%s"
          % (w.n_records, total, len(mistyped), len(notices), complete), flush=True)

    hid = [n for n in notices.values() if n["status"] in ("hidden", "partly_hidden")]
    unsup = [r for r in overflag if not r["rw_either"]]
    need = sorted({t for n in hid for t in n["targets"] if t != n["record"]}
                  | {r["target"] for r in unsup if not r["self"]})
    tmeta = lookup_targets(need)

    for n in notices.values():
        ts = [t for t in n["targets"] if t != n["record"]]
        titles = [tmeta.get(t, {}).get("title", "") for t in ts]
        n["target_titles"] = " ;; ".join(t[:80] for t in titles)
        n["any_target_marked"] = any(retraction_worded(t) for t in titles if t)
        n["utypes"] = ";".join(sorted(n["utypes"]))
        n["n_targets"] = n["n_rel"]
        n["targets"] = ";".join(n["targets"])
    for r in unsup:
        m = tmeta.get(r["target"], {})
        r["t_title"], r["t_type"] = m.get("title", ""), m.get("type", "")
        r["t_marked"] = retraction_worded(m.get("title", "")) if m else ""

    order = sorted(notices.values(), key=lambda n: (n["publisher"], n["record"]))
    write_csv(os.path.join(a.out_dir, "notices_hidden.csv"),
              [n for n in order if n["status"] in ("hidden", "partly_hidden")], NOTICE_FIELDS)
    write_csv(os.path.join(a.out_dir, "notices_covered_on_notice.csv"),
              [n for n in order if n["status"] == "covered_on_notice"], NOTICE_FIELDS)
    write_csv(os.path.join(a.out_dir, "overflag_unsupported.csv"),
              sorted(unsup, key=lambda r: (r["publisher"], r["record"])), OVER_FIELDS)
    pool = [n for n in hid if n["record"] not in AUDIT4_SAMPLE]
    grade = sorted(pool, key=lambda n: sha_key("g4b", n["record"]))[:GRADE_N]
    write_csv(os.path.join(a.out_dir, "grade_notices20.csv"), grade,
              NOTICE_FIELDS + ["grade", "note"])

    status = collections.Counter(n["status"] for n in notices.values())
    hidden_n = [n for n in notices.values() if n["status"] == "hidden"]
    pub = collections.Counter(n["publisher"] for n in hid)
    recent = [n for n in notices.values() if n["year"] is not None and n["year"] >= 2023]
    old = [n for n in notices.values() if n["year"] is not None and n["year"] < 2020]
    pair_hidden_rel = [r for r in mistyped if r["pair_hidden"]]
    summary = {
        "post_hoc": True, "complete": complete, "n_records": w.n_records,
        "total_results": total, "relations": w.n_relations,
        "n_mistyped_relations": len(mistyped),
        "n_pair_hidden_relations": len(pair_hidden_rel),
        "n_pair_hidden_pairs": len({tuple(sorted((r["record"], r["target"])))
                                    for r in pair_hidden_rel}),
        "n_pair_hidden_but_notice_covered": sum(1 for r in pair_hidden_rel if r["notice_covered"]),
        "n_pair_hidden_self": sum(1 for r in pair_hidden_rel if r["self"]),
        "n_pair_hidden_self_covered": sum(1 for r in pair_hidden_rel
                                          if r["self"] and r["notice_covered"]),
        "n_notices": len(notices), "notice_status": dict(status),
        "n_hidden_or_partly": len(hid),
        "hidden_or_partly_members": len({n["member"] for n in hid}),
        "hidden_or_partly_by_publisher": pub.most_common(40),
        "hidden_by_year": dict(sorted(collections.Counter(
            n["year"] for n in hid if n["year"]).items())),
        "hidden_self_only": sum(1 for n in hid if n["self_only"]),
        "hidden_any_target_marked": sum(1 for n in hid if n["any_target_marked"]),
        "hidden_strict_targets": sum(len(n["targets"].split(";")) for n in hidden_n),
        "recent_notices": len(recent),
        "recent_hidden": sum(1 for n in recent if n["status"] in ("hidden", "partly_hidden")),
        "old_notices": len(old),
        "old_hidden": sum(1 for n in old if n["status"] in ("hidden", "partly_hidden")),
        "n_overflag": len(overflag), "n_overflag_unsupported": len(unsup),
        "overflag_unsupported_target_marked": sum(1 for r in unsup if r.get("t_marked") is True),
        "targets_needed": len(need), "targets_found": len(tmeta),
    }
    summary["rate_recent_hidden"] = share(summary["recent_hidden"], summary["recent_notices"])
    summary["rate_old_hidden"] = share(summary["old_hidden"], summary["old_notices"])
    # consistency gate against audit 4 (run 2026-11-08 20:25Z): 350 pair-hidden pairs
    summary["consistent_with_audit4"] = (complete and w.n_records >= 450000
                                         and abs(summary["n_pair_hidden_pairs"] - 350) <= 35)
    summary["http"] = dict(STATS)
    summary["elapsed_s"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: summary[k] for k in ("n_records", "n_pair_hidden_pairs", "notice_status",
                                              "n_overflag_unsupported", "consistent_with_audit4")},
                     default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
