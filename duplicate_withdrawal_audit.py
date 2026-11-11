#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 15 (pre-registered in PREREG-15.md): how many items that Crossref shows as withdrawn in
place are really duplicate DOIs, with the article live under another DOI, and does any metadata
say where it went?

Input: results/audit13/w_only.csv from this repository (audit 13's census). Rows with
self_w == True are the "withdrawn in place" items: every retractive link to them is a publisher
`withdrawal`, Retraction Watch does not list them, and their own record carries the withdrawal
link to itself. For each one, this script reads its Crossref record, searches Crossref by its
title (status mark removed), first author and journal, and judges the top hits:

  duplicate      same type, same title (or nearly the same title and a shared author family name)
  later_version  the hit's DOI is the target's DOI plus a suffix (Cochrane '.pub2' and the like)
  other_version  same title and author, different type (preprint, proceedings paper)
  title_clash    a hit with the same title but different authors (or a very short title)
  none           nothing found

For each duplicate it records whether either record's `relation` or `update-to` points at the
other, whether both sit in the same journal, and OpenAlex's is_retracted for the live copy.

No API keys. raw.githubusercontent.com, api.crossref.org and api.openalex.org (mailto set).
Usage: python duplicate_withdrawal_audit.py --out-dir /out
"""
import argparse
import collections
import csv
import hashlib
import html
import io
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
UA = "crossref-duplicate-withdrawal-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-15.md"
PLAN_MARK = b"Pre-registration 15"
INPUT = "results/audit13/w_only.csv"
EXPECT_W_SELF = 1204
ROWS = 10
T_BATCH = 20
OA_BATCH = 50
GRADE_N = 20
NEAR = 0.8
MIN_TOKENS = 4
ELSEVIER = "Elsevier BV"
SELECT = "DOI,title,container-title,publisher,type,author,relation,update-to,issued"
CONTROLS = {"10.1016/j.beem.2014.05.003": "10.1016/j.beem.2014.07.004",
            "10.1016/j.matpr.2021.04.483": "10.1016/j.matpr.2021.04.451"}
CHECK_NONE = "10.1016/j.jinf.2005.11.080"   # hand-graded genuine in GRADING-13 (reported, not a gate)
RETRACTIVE = {"retraction", "withdrawal", "partial_retraction", "removal"}
SKIP_TYPES = {"peer_review", "component"}
CLASSES = ["duplicate", "later_version", "other_version", "title_clash", "none", "no_title",
           "search_failed"]
ASKABLE = re.compile(r"^10\.\d{4,9}/[^\s|,:&#+?%<>;\"\\]+$")
STATUS_PREFIX = re.compile(
    r"^(?:retracted(?: article)?|withdrawn(?: article)?|removed|temporary removal|"
    r"temporarily removed)\s*[:.\-\]]\s*")
MARK_END = re.compile(r"[\[(]\s*(?:retracted|withdrawn)(?: article)?\s*[\])]$")
LEAD = " \"'[(*"


# ---------------------------------------------------------------- pure helpers
def ascii_fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch if ord(ch) < 128 else ("" if unicodedata.combining(ch) else " ") for ch in s)


def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/",
              "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip()


def norm_type(t):
    return re.sub(r"[\s\-]+", "_", str(t or "").strip().lower())


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v or "")


def words(s):
    return re.findall(r"[a-z0-9]+", ascii_fold(html.unescape(str(s or ""))).lower())


def t_marked(title):
    """Title marked as retracted/withdrawn by its publisher ('WITHDRAWN: ...', '... (Retracted)')."""
    c = re.sub(r"\s+", " ", ascii_fold(title).lower()).strip()
    return bool(STATUS_PREFIX.match(c.lstrip(LEAD)) or MARK_END.search(c))


def clean_title(title):
    """Lower-cased title without the publisher's status mark: 'WITHDRAWN: X' -> 'x'."""
    c = re.sub(r"\s+", " ", ascii_fold(html.unescape(str(title or "")))).strip().lower()
    c = c.lstrip(LEAD)
    m = STATUS_PREFIX.match(c)
    if m:
        c = c[m.end():]
    return MARK_END.sub("", c).strip()


def title_key(title):
    return " ".join(words(clean_title(title)))


def jaccard(a, b):
    x, y = set(title_key(a).split()), set(title_key(b).split())
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


def families(authors):
    out = set()
    for a in authors or []:
        if isinstance(a, dict) and a.get("family"):
            k = " ".join(words(a.get("family")))
            if k:
                out.add(k)
    return out


def first_family(authors):
    for a in authors or []:
        if isinstance(a, dict) and a.get("family") and a.get("sequence") == "first":
            return str(a.get("family"))
    for a in authors or []:
        if isinstance(a, dict) and a.get("family"):
            return str(a.get("family"))
    return ""


def author_match(a, b):
    """True if the two author lists share a family name, False if not, None if either is empty."""
    fa, fb = families(a), families(b)
    if not fa or not fb:
        return None
    return bool(fa & fb)


def linked_dois(item):
    """DOIs a Crossref record points at through `relation` or `update-to`."""
    out = set()
    rel = (item or {}).get("relation") or {}
    if isinstance(rel, dict):
        for v in rel.values():
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, dict) and str(x.get("id-type") or "").lower() == "doi":
                    d = norm_doi(x.get("id"))
                    if d:
                        out.add(d)
    for u in (item or {}).get("update-to") or []:
        if isinstance(u, dict):
            d = norm_doi(u.get("DOI"))
            if d:
                out.add(d)
    return out


def query_text(title, t_item):
    """Search text: cleaned title, first author family name and journal."""
    parts = [clean_title(title)]
    fam = first_family((t_item or {}).get("author"))
    if fam:
        parts.append(" ".join(words(fam)))
    ct = first((t_item or {}).get("container-title"))
    if ct:
        parts.append(" ".join(words(ct)))
    return " ".join(p for p in parts if p)[:300]


def judge(t, t_item, t_title, hit):
    """One search hit as a possible live copy of withdrawn target t; None if it cannot be one."""
    h = norm_doi((hit or {}).get("DOI"))
    if not h or h == t:
        return None
    h_type = norm_type(hit.get("type"))
    if h_type in SKIP_TYPES:
        return None
    h_title = first(hit.get("title"))
    if not h_title or t_marked(h_title):
        return None
    if any(isinstance(u, dict) and norm_type(u.get("type")) in RETRACTIVE
           for u in hit.get("update-to") or []):
        return None
    tk = title_key(t_title)
    exact = bool(tk) and title_key(h_title) == tk
    jac = jaccard(h_title, t_title)
    if not exact and jac < NEAR:
        return None
    t_item = t_item or {}
    t_type = norm_type(t_item.get("type"))
    t_ct = " ".join(words(first(t_item.get("container-title"))))
    h_ct = " ".join(words(first(hit.get("container-title"))))
    return {"doi": h, "title": re.sub(r"\s+", " ", h_title)[:300], "exact": exact,
            "jaccard": round(jac, 3), "ntok": len(tk.split()),
            "author_match": author_match(t_item.get("author"), hit.get("author")),
            "type": h_type, "same_type": bool(t_type) and h_type == t_type,
            "later_version": h.startswith(t + "."),
            "same_journal": bool(t_ct) and t_ct == h_ct,
            "container": re.sub(r"\s+", " ", html.unescape(first(hit.get("container-title"))))[:150],
            "publisher": str(hit.get("publisher") or "")[:80],
            "linked": h in linked_dois(t_item) or t in linked_dois(hit)}


def is_copy(c):
    """A candidate counts as a copy: shared author, or exact title of 4+ words with no authors."""
    if c["author_match"] is True:
        return True
    return c["author_match"] is None and c["exact"] and c["ntok"] >= MIN_TOKENS


def classify(cands):
    """(class, best candidate or None) for one target from its judged candidates."""
    good = [c for c in cands if is_copy(c)]
    ver = [c for c in good if c["later_version"]]
    if ver:
        return "later_version", ver[0]
    dup = [c for c in good if c["same_type"]]
    if dup:
        dup.sort(key=lambda c: (not c["exact"], c["author_match"] is not True, not c["same_journal"]))
        return "duplicate", dup[0]
    if good:
        return "other_version", good[0]
    clash = [c for c in cands if c["exact"]]
    if clash:
        return "title_clash", clash[0]
    return "none", None


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def askable(doi):
    return bool(ASKABLE.match(doi or ""))


def read_input(body):
    """w_self rows (self_w == 'True') of audit 13's w_only.csv, given as bytes."""
    text = body.decode("utf-8-sig")
    return [r for r in csv.DictReader(io.StringIO(text)) if str(r.get("self_w")) == "True"]


# ---------------------------------------------------------------- grading
def grade(c, gates):
    """Predictions P1-P6 of PREREG-15.md from the count dict c."""
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    def ranged(k, num, den, lo, hi, minimum, note):
        if den >= minimum:
            x = share(num, den)
            put(k, x, (lo is None or x >= lo) and (hi is None or x <= hi), note)
        else:
            put(k, den, None, "inconclusive: fewer than %d items (%s)" % (minimum, note))

    ranged("P1", c["m_dup"], c["m_n"], 0.5, 0.9, 30,
           "duplicate share of title-marked w_self items in 50-90%")
    ranged("P2", c["e_dup"], c["e_n"], 0.6, None, 30,
           "duplicate share of title-marked Elsevier w_self items >= 60%")
    ranged("P3", c["u_dup"], c["u_n"], None, 0.4, 30,
           "duplicate share of w_self items without a status mark <= 40%")
    ranged("P4", c["d_unlinked"], c["d_n"], 0.8, None, 30,
           "neither record links the other in >= 80% of duplicate pairs")
    ranged("P5", c["d_same_journal"], c["d_n"], 0.5, None, 30,
           "live copy in the same journal for >= 50% of duplicate pairs")
    ranged("P6", c["h_flag"], c["h_found"], None, 0.02, 30,
           "OpenAlex is_retracted true for <= 2% of found live copies")
    if not all(g.get("ok") for g in gates.values()):
        for k in res:
            res[k]["note"] += " (a gate failed: reported descriptively, not graded)"
    return res


# ---------------------------------------------------------------- network
STATS = collections.Counter()
_LAST = {}


def http(url, tries=6, timeout=120, gap=0.5, host="x"):
    delay = 5
    last = -1
    for _ in range(tries):
        wait = _LAST.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
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
        obj = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None
    return obj if isinstance(obj, dict) else None


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def wait_for_plan(minutes):
    deadline = time.monotonic() + 60 * minutes
    while True:
        st, b = http(RAW + PLAN, tries=1, host="gh", gap=1.0)
        if st == 200 and PLAN_MARK in b:
            return now()
        if time.monotonic() >= deadline:
            return None
        time.sleep(60)


def fetch_records(dois):
    """({doi: Crossref item}, requests, failed requests)."""
    out, n_b, n_fail = {}, 0, 0
    ok = [d for d in dois if askable(d)]
    for i in range(0, len(ok), T_BATCH):
        b = ok[i:i + T_BATCH]
        n_b += 1
        url = ("%s?filter=%s&rows=%d&select=%s&mailto=%s"
               % (CROSSREF, ",".join("doi:" + urllib.parse.quote(d, safe="/()") for d in b),
                  2 * T_BATCH, SELECT, MAILTO))
        st, body = http(url, host="crossref", gap=0.5)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            n_fail += 1
            continue
        for it in msg.get("items") or []:
            out[norm_doi(it.get("DOI"))] = it
    for d in dois:
        if askable(d):
            continue
        n_b += 1
        st, body = http("%s/%s?mailto=%s" % (CROSSREF, urllib.parse.quote(d, safe="/()"), MAILTO),
                        host="crossref", gap=0.5)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            n_fail += 1
            continue
        out[norm_doi(msg.get("DOI"))] = msg
    return out, n_b, n_fail


def search(text):
    url = ("%s?query.bibliographic=%s&rows=%d&select=%s&mailto=%s"
           % (CROSSREF, urllib.parse.quote_plus(text), ROWS, SELECT, MAILTO))
    st, body = http(url, host="crossref", gap=0.5)
    msg = (jload(body) or {}).get("message") if st == 200 else None
    if not isinstance(msg, dict):
        return None
    return msg.get("items") or []


def openalex(dois):
    """({doi: is_retracted}, batches asked, batches failed). Only askable DOIs."""
    out = {}
    ok = [d for d in dois if askable(d)]
    n_b = n_fail = 0
    for i in range(0, len(ok), OA_BATCH):
        b = ok[i:i + OA_BATCH]
        n_b += 1
        url = ("%s?filter=doi:%s&select=doi,is_retracted&per-page=100&mailto=%s"
               % (OPENALEX, "|".join(urllib.parse.quote(d, safe="/()") for d in b), MAILTO))
        st, body = http(url, host="openalex", gap=0.2)
        obj = jload(body) if st == 200 else None
        if obj is None:
            n_fail += 1
            continue
        for r in obj.get("results") or []:
            out[norm_doi(r.get("doi"))] = r.get("is_retracted")
    return out, n_b, n_fail


# ---------------------------------------------------------------- main
FIELDS = ["target", "publisher", "title_marked", "target_title", "target_journal", "class",
          "copy_doi", "copy_title", "copy_journal", "copy_publisher", "copy_type", "exact",
          "jaccard", "author_match", "same_journal", "linked", "copy_is_retracted",
          "target_is_retracted", "n_candidates", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=180)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    s = {"preregistered": PLAN, "started": now()}
    s["plan_live_at"] = wait_for_plan(a.wait_min)

    def dump():
        with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1, ensure_ascii=False, default=str)

    if not s["plan_live_at"]:
        s["error"] = "plan not live; nothing run"
        dump()
        return 0
    s["data_started"] = now()

    st, body = http(RAW + INPUT, host="gh", gap=1.0)
    rows = read_input(body) if st == 200 else []
    targets = sorted({norm_doi(r.get("target")) for r in rows if r.get("target")})
    by_t = {norm_doi(r.get("target")): r for r in rows}
    print("input: %d w_self rows" % len(targets), flush=True)

    recs, rec_req, rec_fail = fetch_records(targets)
    print("records: %d of %d (%d failed requests)" % (len(recs), len(targets), rec_fail), flush=True)

    out, n_search, n_search_fail = [], 0, 0
    for i, t in enumerate(targets):
        r = by_t[t]
        item = recs.get(t) or {}
        title = first(item.get("title")) or r.get("crossref_title") or ""
        o = {"target": t, "publisher": r.get("publisher") or item.get("publisher") or "",
             "title_marked": t_marked(title), "target_title": re.sub(r"\s+", " ", title)[:300],
             "target_journal": html.unescape(first(item.get("container-title")))[:150],
             "target_is_retracted": r.get("is_retracted", "")}
        if len(title_key(title).split()) < 2:
            o.update({"class": "no_title", "n_candidates": 0})
            out.append(o)
            continue
        n_search += 1
        hits = search(query_text(title, item))
        if hits is None:
            n_search_fail += 1
            o.update({"class": "search_failed", "n_candidates": 0})
            out.append(o)
            continue
        cands = [c for c in (judge(t, item, title, h) for h in hits) if c]
        cls, best = classify(cands)
        o.update({"class": cls, "n_candidates": len(cands)})
        if best:
            o.update({"copy_doi": best["doi"], "copy_title": best["title"],
                      "copy_journal": best["container"], "copy_publisher": best["publisher"],
                      "copy_type": best["type"], "exact": best["exact"], "jaccard": best["jaccard"],
                      "author_match": best["author_match"], "same_journal": best["same_journal"],
                      "linked": best["linked"]})
        out.append(o)
        if (i + 1) % 100 == 0:
            print("searched %d/%d, %.0fs" % (i + 1, len(targets), time.monotonic() - t0), flush=True)

    dups = [o for o in out if o["class"] == "duplicate"]
    oa, oa_b, oa_fail = openalex(sorted({o["copy_doi"] for o in dups}))
    for o in dups:
        o["copy_is_retracted"] = oa.get(o["copy_doi"], "")

    marked = [o for o in out if o["title_marked"]]
    unmarked = [o for o in out if not o["title_marked"]]
    els = [o for o in marked if o["publisher"] == ELSEVIER]
    found = [o for o in dups if o["copy_doi"] in oa]
    c = {"m_n": len(marked), "m_dup": sum(1 for o in marked if o["class"] == "duplicate"),
         "e_n": len(els), "e_dup": sum(1 for o in els if o["class"] == "duplicate"),
         "u_n": len(unmarked), "u_dup": sum(1 for o in unmarked if o["class"] == "duplicate"),
         "d_n": len(dups), "d_unlinked": sum(1 for o in dups if not o["linked"]),
         "d_same_journal": sum(1 for o in dups if o["same_journal"]),
         "h_found": len(found), "h_flag": sum(1 for o in found if oa[o["copy_doi"]] is True)}

    by = {o["target"]: o for o in out}
    ctrl = {t: [by.get(t, {}).get("class"), by.get(t, {}).get("copy_doi")] for t in CONTROLS}
    gates = {
        "G1_input": {"value": [st, len(targets)], "ok": st == 200 and len(targets) == EXPECT_W_SELF},
        "G2_controls": {"value": ctrl,
                        "ok": all(ctrl[t] == ["duplicate", d] for t, d in CONTROLS.items())},
        "G3_failures": {"value": {"records": [rec_fail, rec_req], "search": [n_search_fail, n_search],
                                  "openalex": [oa_fail, oa_b]},
                        "ok": rec_fail <= 0.02 * max(rec_req, 1)
                        and n_search_fail <= 0.02 * max(n_search, 1)
                        and oa_fail <= 0.02 * max(oa_b, 1)},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(c, gates)

    write_csv(os.path.join(a.out_dir, "w_self_copies.csv"), out)
    write_csv(os.path.join(a.out_dir, "grade20_duplicate.csv"),
              sorted(dups, key=lambda o: sha_key("a15g", o["target"]))[:GRADE_N])
    write_csv(os.path.join(a.out_dir, "grade20_marked_none.csv"),
              sorted([o for o in marked if o["class"] == "none"],
                     key=lambda o: sha_key("a15n", o["target"]))[:GRADE_N])

    cls_all = collections.Counter(o["class"] for o in out)
    cls_pub = collections.defaultdict(collections.Counter)
    for o in out:
        cls_pub[o["publisher"]][o["class"]] += 1
    top = sorted(cls_pub.items(), key=lambda kv: -sum(kv[1].values()))[:15]
    s.update({
        "n_w_self": len(targets), "n_records_read": len(recs), "classes": {k: cls_all[k] for k in CLASSES},
        "classes_marked": dict(collections.Counter(o["class"] for o in marked)),
        "classes_unmarked": dict(collections.Counter(o["class"] for o in unmarked)),
        "classes_by_publisher": {p: dict(cn) for p, cn in top},
        "counts": c, "check_none": [by.get(CHECK_NONE, {}).get("class"), by.get(CHECK_NONE, {}).get("copy_doi")],
        "dup_exact": sum(1 for o in dups if o.get("exact")),
        "dup_author_true": sum(1 for o in dups if o.get("author_match") is True),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()), "predictions": preds,
        "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    dump()
    print(json.dumps({"classes": s["classes"], "counts": c, "gates_ok": s["all_gates_ok"],
                      "predictions": {k: x["held"] for k, x in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
