#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 16, step P7b (promised in PREREG-16.md): check Retraction Watch again, by title.

Audit 16 matched the 28 Cochrane review versions withdrawn since 2019-07-01 to the Retraction
Watch CSV by DOI (and by CD number within 365 days). PREREG-16 promised that every one RW does
not list would be checked again by title. This script does that for all 28 (the 7 RW lists act
as controls). For each withdrawn version it reads the title from Crossref, then scans every RW
row (any journal, any nature) for:
  title_exact  the normalised title equals RW's Title
  title_close  word-set Jaccard >= 0.8 (titles of 4+ words)
  cd           the CD number appears in RW's OriginalPaperDOI or RetractionDOI
  notice       RW's RetractionDOI is the withdrawal notice's DOI

No API keys. api.crossref.org, gitlab.com. Usage: python cochrane_rw_title_check.py --out-dir /out
"""
import argparse
import collections
import csv
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAILTO = "mv2@munimtech.com"
UA = "cochrane-rw-title-check/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works/"
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
csv.field_size_limit(1 << 24)
P = "10.1002/14651858."
# (withdrawn version, withdrawal notice, listed by RW's DOI in audit 16)
TARGETS = [
    ("cd001024.pub2", "cd001024.pub3", False), ("cd002236.pub2", "cd002236.pub3", False),
    ("cd003029.pub3", "cd003029.pub4", False), ("cd003547.pub3", "cd003547.pub4", False),
    ("cd003622.pub2", "cd003622.pub3", False), ("cd003808.pub3", "cd003808.pub4", True),
    ("cd003814.pub2", "cd003814.pub3", True), ("cd003815.pub4", "cd003815.pub5", True),
    ("cd004060.pub2", "cd004060.pub3", False), ("cd004397.pub2", "cd004397.pub3", False),
    ("cd004833.pub3", "cd004833.pub4", True), ("cd004986.pub3", "cd004986.pub4", False),
    ("cd005160.pub2", "cd005160.pub3", False), ("cd005264.pub2", "cd005264.pub3", False),
    ("cd005639.pub2", "cd005639.pub3", False), ("cd006141.pub2", "cd006141.pub3", False),
    ("cd007376.pub2", "cd007376.pub3", False), ("cd007705.pub2", "cd007705.pub3", False),
    ("cd008033.pub3", "cd008033.pub4", True), ("cd008359.pub2", "cd008359.pub3", False),
    ("cd009046.pub2", "cd009046.pub3", False), ("cd009051.pub2", "cd009051.pub3", False),
    ("cd009325.pub2", "cd009325.pub3", False), ("cd010937.pub2", "cd010937.pub3", True),
    ("cd011313.pub3", "cd011313.pub4", True), ("cd011823.pub2", "cd011823.pub3", False),
    ("cd012271.pub2", "cd012271.pub3", False), ("cd013326.pub2", "cd013326.pub3", False),
]
CONTROL = "cd011313.pub3"   # RW record 25814 lists it by DOI (audit 16, G3)
PREFIXES = ("withdrawn", "retracted", "retraction", "withdrawal")


# ---------------------------------------------------------------- pure helpers
def norm_title(t):
    """Lower-case words of a title, without tags, punctuation or a WITHDRAWN:/RETRACTED: prefix."""
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(t or ""))).lower()
    t = re.sub(r"[^0-9a-z]+", " ", t).strip()
    words = t.split()
    while words and words[0] in PREFIXES:
        words = words[1:]
    return " ".join(words)


def jaccard(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cd_of(v):
    m = re.match(r"^(cd\d{6})", v)
    return m.group(1) if m else ""


def row_matches(row, title_n, cd, notice_doi):
    """List of match kinds between one RW row (dict) and one target."""
    how = []
    rt = norm_title(row.get("Title"))
    if title_n and rt:
        if rt == title_n:
            how.append("title_exact")
        elif len(title_n.split()) >= 4 and jaccard(rt, title_n) >= 0.8:
            how.append("title_close")
    dois = (str(row.get("OriginalPaperDOI") or "") + " " + str(row.get("RetractionDOI") or "")).lower()
    if cd and re.search(r"14651858\." + cd + r"(?![0-9])", dois):
        how.append("cd")
    if notice_doi and notice_doi in str(row.get("RetractionDOI") or "").lower():
        how.append("notice")
    return how


def scan(rows, targets):
    """{target: [match dicts]} for targets = {target: (title_n, cd, notice_doi)}."""
    out = {t: [] for t in targets}
    n = 0
    for row in rows:
        n += 1
        for t, (title_n, cd, notice) in targets.items():
            how = row_matches(row, title_n, cd, notice)
            if how:
                out[t].append({"id": str(row.get("Record ID") or "").strip(),
                               "nature": str(row.get("RetractionNature") or "").strip(),
                               "date": str(row.get("RetractionDate") or "").strip(),
                               "orig_doi": str(row.get("OriginalPaperDOI") or "").strip(),
                               "notice_doi": str(row.get("RetractionDOI") or "").strip(),
                               "journal": str(row.get("Journal") or "").strip()[:60],
                               "reason": str(row.get("Reason") or "").strip()[:200],
                               "how": "+".join(how)})
    return out, n


# ---------------------------------------------------------------- network
STATS = collections.Counter()


def http(url, tries=5, timeout=120):
    delay = 5
    for _ in range(tries):
        time.sleep(0.5)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["http_%d" % r.status] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            STATS["http_%d" % e.code] += 1
            if e.code in (400, 404, 410):
                return e.code, b""
        except Exception:
            STATS["neterr"] += 1
        time.sleep(delay)
        delay = min(delay * 2, 60)
    return -1, b""


def crossref_title(doi):
    st, body = http(CROSSREF + urllib.parse.quote(doi, safe="/") + "?mailto=" + MAILTO)
    if st != 200:
        return ""
    try:
        t = json.loads(body.decode("utf-8"))["message"].get("title") or [""]
        return t[0] if isinstance(t, list) and t else str(t)
    except (ValueError, KeyError, UnicodeDecodeError, AttributeError, TypeError):
        return ""


def download(tmp):
    for u in RW_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            return u
        except Exception as e:
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tmp", default="/tmp/retraction_watch.csv")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    s = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    targets, titles = {}, {}
    for v, notice, _ in TARGETS:
        t = crossref_title(P + v)
        titles[v] = t
        targets[v] = (norm_title(t), cd_of(v), P + notice)
    src = download(a.tmp)
    s["rw_source"] = src
    found, n = {}, 0
    if src:
        with open(a.tmp, encoding="utf-8-sig", errors="replace", newline="") as f:
            found, n = scan(csv.DictReader(f), targets)
    s["rw_rows"] = n
    rows = []
    for v, notice, listed in TARGETS:
        m = found.get(v, [])
        rows.append({"target": P + v, "notice": P + notice, "listed_by_doi_a16": listed,
                     "title": titles[v], "n_rw_rows": len(m),
                     "rw_by_title": any("title" in x["how"] for x in m),
                     "rw_by_cd": any("cd" in x["how"] for x in m),
                     "rw_by_notice": any("notice" in x["how"] for x in m),
                     "rw_rows": json.dumps(m, ensure_ascii=False)})
    with open(os.path.join(a.out_dir, "title_check.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    unl = [r for r in rows if not r["listed_by_doi_a16"]]
    ctl = [r for r in rows if r["target"] == P + CONTROL][0]
    s.update({
        "titles_found": sum(1 for v in titles.values() if v),
        "gate_rw_rows_ge_60000": n >= 60000,
        "gate_control_found_by_title": bool(ctl["rw_by_title"]),
        "listed_by_doi_found_by_title": sum(1 for r in rows if r["listed_by_doi_a16"] and r["rw_by_title"]),
        "unlisted": len(unl),
        "unlisted_found_any": [r["target"] for r in unl if r["n_rw_rows"]],
        "unlisted_found_by_title": [r["target"] for r in unl if r["rw_by_title"]],
        "http": dict(STATS),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: s[k] for k in ("rw_rows", "titles_found", "gate_control_found_by_title",
                                         "unlisted", "unlisted_found_any")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
