# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Crossref update audit 7 (pre-registered in PREREG-7.md): papers that Crossref shows as
retracted or withdrawn only because their CORRECTION was retracted or withdrawn.

Hand grading of audit 5 (GRADING-5.md) found Elsevier records titled "RETRACTED: Corrigendum
to ...", "WITHDRAWN: Corrigendum to ..." or "WITHDRAWN: Erratum" whose own `update-to` link to
the corrected paper carries the type `retraction`, `withdrawal` or `removal`. Crossref, and tools
that read it, then show the PAPER as retracted or withdrawn, although only its correction was.
In two verified cases the notice that retracts the correction ("Retraction notice to
Corrigendum to ...") is itself deposited with the type `erratum`: the two types look swapped.

This script walks every Crossref record matched by filter=update-type:X (X = retraction,
withdrawal, partial_retraction, removal), keeps publisher-sourced retractive relations
notice -> target (target != notice), and classifies each notice title:

- rc:         a retracted/withdrawn/removed correction ("RETRACTED: Corrigendum to ...",
              "WITHDRAWN: Erratum", "TEMPORARY REMOVAL: Corrigendum to ...");
- rn:         a retraction notice OF a correction ("Retraction notice to Corrigendum to ...",
              "Retraction: Corrigendum: ...", "Retraction Note: Correction to: ...");
- correction: any other title with a correction word (errat, corrig, correction, addend);
- empty / plain: everything else.

For every rc relation (N -> T) it asks whether anything else says T is retracted:
`rw` (a Retraction Watch retractive relation to T), `self` (T's own record carries a
retractive update to itself), `notice` (a retractive publisher relation to T from a plain or
untitled notice), `title` (T's Crossref title is marked RETRACTED/WITHDRAWN). Verdict:
`also_retracted` if any, else `only_via_rc`. For each rc notice it reads the notices that
update it (filter=updates:N) and records `swap` (a publisher notice titled as a retraction or
withdrawal notice updates N with a non-retractive type), `retractive_notice`, `rw_only` or
`none`. For only_via_rc targets it reads OpenAlex is_retracted and cited_by_count.

No API keys. api.crossref.org and api.openalex.org (mailto set).
Usage: python retracted_correction_audit.py --out-dir /out
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
UA = "crossref-retracted-correction-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
SELECT = "DOI,update-to,title,type,publisher,member,created,container-title"
UPDATE_TYPES = ["retraction", "withdrawal", "partial_retraction", "removal"]
RETRACTIVE = set(UPDATE_TYPES)
UPDATES_BATCH = 10
GRADE_N = 20
ELSEVIER = "Elsevier BV"

DASHES = "‐‑‒–—―−"
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
STATUS_PREFIX = re.compile(
    r"^(?:retracted(?: article)?|withdrawn(?: article)?|removed|temporary removal|"
    r"temporarily removed)\s*[:.\-\]]\s*")
NOTICE_HEAD = re.compile(
    r"^(?:notice of (?:retraction|withdrawal)|retraction|withdrawal|removal|partial retraction)\b"
    r"(?:\s+(?:notice|note))?(?:\s+(?:to|of|for))?\s*[:.\-]?\s*")
CORR_HEAD = re.compile(
    r"^(?:corrigendum|corrigenda|erratum|errata|correction|corrections|author correction|"
    r"publisher correction|addendum|addenda)\b")
CORRECT_WORD = re.compile(r"errat|corrig|correction|addend")
MARK_END = re.compile(r"[\[(]\s*(?:retracted|withdrawn)(?: article)?\s*[\])]$")
LEAD = " \"'[("

# instrument check (G2), each verified by hand against live Crossref records on 2026-11-09
ONLY_CASES = [
    ("10.1016/j.lfs.2022.120407", "10.1016/j.lfs.2008.11.017"),
    ("10.1016/j.ijpx.2025.100319", "10.1016/j.ijpx.2023.100203"),
    ("10.1016/j.clnu.2019.01.017", "10.1016/j.clnu.2016.12.027"),
    ("10.1016/j.neuro.2023.12.014", "10.1016/j.neuro.2020.12.005"),
    ("10.1016/j.neuroscience.2023.06.011", "10.1016/j.neuroscience.2022.11.029"),
]
ALSO_CASES = [("10.1016/j.heliyon.2023.e23950", "10.1016/j.heliyon.2021.e06952")]
SWAP_CASES = ["10.1016/j.lfs.2022.120407", "10.1016/j.ijpx.2025.100319"]
G2_TARGETS = {t for _, t in ONLY_CASES + ALSO_CASES}


# ---------------------------------------------------------------- pure helpers
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


def notice_class(title):
    """'rc' | 'rn' | 'correction' | 'empty' | 'plain' for the title of a notice record."""
    c = core_title(title)
    if not c:
        return "empty"
    m = STATUS_PREFIX.match(c)
    if m and CORR_HEAD.match(c[m.end():].lstrip(LEAD)):
        return "rc"
    m = NOTICE_HEAD.match(c)
    if m and CORR_HEAD.match(c[m.end():].lstrip(LEAD)):
        return "rn"
    if CORRECT_WORD.search(c):
        return "correction"
    return "plain"


def notice_worded(title):
    """Title reads as a retraction/withdrawal notice ('Retraction notice to ...')."""
    return bool(NOTICE_HEAD.match(core_title(title)))


def t_marked(title):
    """Crossref title of a paper marked as retracted/withdrawn by its publisher."""
    c = clean_title(title)
    return bool(STATUS_PREFIX.match(c.lstrip(LEAD + "*")) or MARK_END.search(c))


def t_is_correction(title):
    c = core_title(title)
    return bool(CORR_HEAD.match(c)) or notice_class(title) == "rc"


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


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


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


# ---------------------------------------------------------------- Crossref walk
class Walker:
    """Collects retractive relations from notice records (deduplicated by record DOI)."""

    def __init__(self):
        self.seen = set()
        self.rels = []              # publisher-sourced retractive relations, notice != target
        self.self_retracted = set()  # records whose own update-to points at themselves
        self.rw_retracted = set()    # targets of a retraction-watch retractive relation
        self.sources = collections.Counter()
        self.n_records = 0

    def add(self, item):
        rec = norm_doi(item.get("DOI"))
        if not rec or rec in self.seen:
            return
        self.seen.add(rec)
        self.n_records += 1
        title = first(item.get("title"))
        nclass = notice_class(title)
        keep = set()
        for u in item.get("update-to") or []:
            if not isinstance(u, dict):
                continue
            t, ut, src = norm_doi(u.get("DOI")), norm_type(u.get("type")), str(u.get("source") or "")
            if ut not in RETRACTIVE or not t:
                continue
            self.sources[src] += 1
            if src == "retraction-watch":
                self.rw_retracted.add(t)
                continue
            if src != "publisher":
                continue
            if t == rec:
                self.self_retracted.add(t)
                continue
            if (t, ut) in keep:
                continue
            keep.add((t, ut))
            self.rels.append({
                "notice": rec, "target": t, "utype": ut, "nclass": nclass,
                "member": str(item.get("member") or ""),
                "publisher": str(item.get("publisher") or ""), "year": created_year(item),
                "notice_title": title[:200], "container": first(item.get("container-title"))[:80]})


def evidence(target, w, plain_targets, t_title):
    ev = []
    if target in w.rw_retracted:
        ev.append("rw")
    if target in w.self_retracted:
        ev.append("self")
    if target in plain_targets:
        ev.append("notice")
    if t_title and t_marked(t_title):
        ev.append("title")
    return ev


def add_updates(out, item, wanted):
    """Record every update-to entry of `item` that points at a DOI in `wanted`."""
    r = norm_doi(item.get("DOI"))
    title = first(item.get("title"))
    for u in item.get("update-to") or []:
        if not isinstance(u, dict):
            continue
        t = norm_doi(u.get("DOI"))
        if t in wanted and r and r != t:
            out.setdefault(t, []).append(
                (r, norm_type(u.get("type")), str(u.get("source") or ""), title[:200]))


def notice_status(entries):
    pub = [e for e in entries if e[2] == "publisher"]
    if any(e[1] in RETRACTIVE for e in pub):
        return "retractive_notice"
    if any(e[1] not in RETRACTIVE and notice_worded(e[3]) for e in pub):
        return "swap"
    if any(e[2] == "retraction-watch" and e[1] in RETRACTIVE for e in entries):
        return "rw_only"
    return "none"


# ---------------------------------------------------------------- summary
def oa_groups(only):
    by_t = {}
    for r in only:
        g = by_t.setdefault(r["target"], {"utypes": set(), "oa": r.get("oa_is_retracted"),
                                          "cites": r.get("oa_cited_by")})
        g["utypes"].add(r["utype"])
    out = {"retraction": [0, 0], "other": [0, 0]}  # [checked, flagged retracted]
    cites = 0
    for g in by_t.values():
        grp = "retraction" if "retraction" in g["utypes"] else "other"
        if g["oa"] in (True, False):
            out[grp][0] += 1
            if g["oa"] is True:
                out[grp][1] += 1
        try:
            cites += int(g["cites"] or 0)
        except (TypeError, ValueError):
            pass
    return out, cites


def status_counts(only):
    res = {"retraction": collections.Counter(), "other": collections.Counter()}
    for r in only:
        grp = "retraction" if r["utype"] == "retraction" else "other"
        res[grp][r.get("n_status") or "unknown"] += 1
    return {k: dict(v) for k, v in res.items()}


def known_share(counts, key):
    known = sum(n for k, n in counts.items() if k != "unknown")
    return share(counts.get(key, 0), known)


def tally(rels, key):
    return collections.Counter(r[key] for r in rels).most_common()


def summarize(w, rc, rn, walk_ok):
    only = [r for r in rc if r["verdict"] == "only_via_rc"]
    also = [r for r in rc if r["verdict"] == "also_retracted"]
    oa, cites = oa_groups(only)
    st = status_counts(only)
    ev = collections.Counter(e for r in also for e in str(r.get("evidence") or "").split(";") if e)
    by_pair = {(r["notice"], r["target"]): r for r in rc}
    by_notice = {}
    for r in rc:
        by_notice.setdefault(r["notice"], r)
    g2_only = {"%s -> %s" % p: (by_pair[p]["verdict"] if p in by_pair else "missing")
               for p in ONLY_CASES}
    g2_also = {"%s -> %s" % p: (by_pair[p]["verdict"] if p in by_pair else "missing")
               for p in ALSO_CASES}
    g2_swap = {n: (by_notice[n].get("n_status") if n in by_notice else "missing")
               for n in SWAP_CASES}
    g2_pass = (all(v == "only_via_rc" for v in g2_only.values())
               and all(v == "also_retracted" for v in g2_also.values())
               and all(v == "swap" for v in g2_swap.values()))
    rn_fetched = [r for r in rn if r.get("t_title")]
    return {
        "walk_complete": walk_ok, "n_records": w.n_records, "sources": dict(w.sources),
        "n_publisher_relations": len(w.rels), "n_self_retracted": len(w.self_retracted),
        "nclass_relations": dict(collections.Counter(r["nclass"] for r in w.rels)),
        "n_rc_relations": len(rc), "n_rc_notices": len({r["notice"] for r in rc}),
        "n_rc_targets": len({r["target"] for r in rc}),
        "rc_by_publisher": tally(rc, "publisher")[:20],
        "share_elsevier": share(sum(1 for r in rc if r["publisher"] == ELSEVIER), len(rc)),
        "rc_by_utype": tally(rc, "utype"),
        "rc_by_year": sorted(collections.Counter(r["year"] for r in rc).items(), key=lambda x: str(x[0])),
        "verdicts": dict(collections.Counter(r["verdict"] for r in rc)),
        "n_only": len(only), "share_only": share(len(only), len(rc)),
        "n_only_targets": len({r["target"] for r in only}),
        "only_by_publisher": tally(only, "publisher")[:20], "only_by_utype": tally(only, "utype"),
        "also_evidence": dict(ev),
        "oa_only_targets": oa, "oa_only_citations": cites,
        "only_status": st,
        "swap_share_retraction": known_share(st["retraction"], "swap"),
        "none_share_other": known_share(st["other"], "none"),
        "g2_only": g2_only, "g2_also": g2_also, "g2_swap": g2_swap, "g2_pass": g2_pass,
        "n_rn_relations": len(rn), "n_rn_target_titles": len(rn_fetched),
        "rn_points_at_non_correction": sum(1 for r in rn_fetched if not t_is_correction(r["t_title"])),
        "rn_by_publisher": tally(rn, "publisher")[:10],
    }


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = {}


def http(url, data=None, tries=6, timeout=120, gap=0.5, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                STATS["%s_%d" % (host, r.status)] += 1
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = e.code
            STATS["%s_%d" % (host, e.code)] += 1
            if e.code in (400, 404, 410, 414):
                return e.code, b""
            time.sleep(delay)
            delay = min(delay * 2, 120)
        except Exception:
            STATS["%s_neterr" % host] += 1
            time.sleep(delay)
            delay = min(delay * 2, 120)
    return last, b""


def jload(body):
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None


def walk(w, utype, max_pages):
    cursor, total = "*", None
    for page in range(max_pages):
        url = ("%s?filter=update-type:%s&rows=1000&select=%s&mailto=%s&cursor=%s"
               % (CROSSREF, utype, SELECT, MAILTO, urllib.parse.quote(cursor, safe="")))
        st, body = http(url, host="crossref", gap=0.3)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            print("walk %s page %d failed: %s" % (utype, page, st), file=sys.stderr, flush=True)
            return False, total
        total = msg.get("total-results", total)
        items = msg.get("items") or []
        if not items:
            return True, total
        for it in items:
            w.add(it)
        cursor = msg.get("next-cursor") or ""
        if not cursor:
            return True, total
        if page % 20 == 0:
            print("%s: %d records after page %d (total %s)" % (utype, w.n_records, page + 1, total),
                  flush=True)
    return False, total


def crossref_titles(dois):
    out = {}
    for i in range(0, len(dois), 20):
        b = [d for d in dois[i:i + 20] if "," not in d]
        if not b:
            continue
        f = ",".join("doi:" + urllib.parse.quote(d, safe="/") for d in b)
        st, body = http("%s?filter=%s&rows=%d&select=DOI,title&mailto=%s"
                        % (CROSSREF, f, len(b) + 5, MAILTO), host="crossref", gap=0.3)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        for it in (msg or {}).get("items") or []:
            out[norm_doi(it.get("DOI"))] = first(it.get("title"))[:200]
    return out


def updates_lookup(notices):
    """({notice: [(r, type, source, r_title)]}, failed set) via filter=updates:<notice>."""
    out = {n: [] for n in notices}
    failed = {n for n in notices if "," in n}
    ok = [n for n in notices if "," not in n]
    run_fail = 0
    for i in range(0, len(ok), UPDATES_BATCH):
        b = ok[i:i + UPDATES_BATCH]
        f = ",".join("updates:" + urllib.parse.quote(d, safe="/") for d in b)
        st, body = http("%s?filter=%s&rows=200&select=DOI,title,update-to&mailto=%s"
                        % (CROSSREF, f, MAILTO), host="crossref", gap=0.3)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            failed.update(b)
            run_fail += 1
            if run_fail >= 10:
                print("updates: 10 batches in a row failed, stopping", file=sys.stderr, flush=True)
                failed.update(ok[i + UPDATES_BATCH:])
                break
            continue
        run_fail = 0
        bset = set(b)
        for it in msg.get("items") or []:
            add_updates(out, it, bset)
    return out, failed


def openalex(dois):
    out = {}
    ok = [d for d in dois if "|" not in d and "," not in d]
    run_fail, aborted = 0, False
    for i in range(0, len(ok), 50):
        b = ok[i:i + 50]
        url = ("%s?filter=doi:%s&select=doi,is_retracted,cited_by_count&per-page=100&mailto=%s"
               % (OPENALEX, "|".join(urllib.parse.quote(d, safe="/()") for d in b), MAILTO))
        st, body = http(url, host="openalex", gap=0.2)
        obj = jload(body) if st == 200 else None
        if obj is None:
            run_fail += 1
            if run_fail >= 5:
                aborted = True
                print("openalex: 5 batches in a row failed, stopping", file=sys.stderr, flush=True)
                break
            continue
        run_fail = 0
        for r in obj.get("results") or []:
            out[norm_doi(r.get("doi"))] = (r.get("is_retracted"), r.get("cited_by_count"))
    return out, aborted


# ---------------------------------------------------------------- main
FIELDS = ["notice", "target", "utype", "nclass", "verdict", "evidence", "n_status", "n_updates",
          "publisher", "member", "year", "container", "notice_title", "t_title",
          "oa_is_retracted", "oa_cited_by", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=400)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()

    w = Walker()
    walk_ok, totals = True, {}
    for ut in UPDATE_TYPES:
        ok, tot = walk(w, ut, a.max_pages)
        totals[ut] = tot
        if ut in ("retraction", "withdrawal"):
            walk_ok = walk_ok and ok
    rc = [r for r in w.rels if r["nclass"] == "rc"]
    rn = [r for r in w.rels if r["nclass"] == "rn"]
    plain_targets = {r["target"] for r in w.rels if r["nclass"] in ("plain", "empty")}
    print("walk done: %d records, %d relations, %d rc, %d rn, %.0fs"
          % (w.n_records, len(w.rels), len(rc), len(rn), time.monotonic() - t0), flush=True)

    targets = sorted({r["target"] for r in rc + rn})
    titles = crossref_titles(targets)
    for r in rc + rn:
        r["t_title"] = titles.get(r["target"], "")
    for r in rc:
        ev = evidence(r["target"], w, plain_targets, r["t_title"])
        r["evidence"] = ";".join(ev)
        r["verdict"] = "also_retracted" if ev else "only_via_rc"

    notices = sorted({r["notice"] for r in rc})
    ups, failed = updates_lookup(notices)
    for r in rc:
        if r["notice"] in failed:
            r["n_status"], r["n_updates"] = "unknown", ""
            continue
        ent = ups.get(r["notice"], [])
        r["n_status"] = notice_status(ent)
        r["n_updates"] = ";".join("%s:%s:%s" % (e[0], e[1], e[2]) for e in ent)[:400]

    only = [r for r in rc if r["verdict"] == "only_via_rc"]
    oa, oa_aborted = openalex(sorted({r["target"] for r in only}))
    for r in only:
        r["oa_is_retracted"], r["oa_cited_by"] = oa.get(r["target"], ("", ""))

    write_csv(os.path.join(a.out_dir, "rc_relations.csv"),
              sorted(rc, key=lambda r: (r["publisher"], r["target"], r["notice"])))
    write_csv(os.path.join(a.out_dir, "only_via_rc.csv"),
              sorted(only, key=lambda r: (r["publisher"], r["target"], r["notice"])))
    pool = [r for r in only if r["target"] not in G2_TARGETS]
    write_csv(os.path.join(a.out_dir, "grade20.csv"),
              sorted(pool, key=lambda r: sha_key("a7", r["notice"], r["target"]))[:GRADE_N])
    write_csv(os.path.join(a.out_dir, "rn_relations.csv"),
              sorted(rn, key=lambda r: (r["publisher"], r["target"], r["notice"])))

    s = summarize(w, rc, rn, walk_ok)
    s.update({"preregistered": "PREREG-7.md", "crossref_totals": totals,
              "n_target_titles_fetched": len(titles), "n_targets_asked": len(targets),
              "n_rc_notices_updates_failed": len(failed), "openalex_aborted": oa_aborted,
              "n_oa_found": len(oa), "http": dict(STATS),
              "elapsed_s": round(time.monotonic() - t0, 1)})
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: s[k] for k in ("n_records", "n_rc_relations", "verdicts", "share_only",
                                        "g2_pass")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
