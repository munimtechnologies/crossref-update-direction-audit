#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 14 (pre-registered in PREREG-14.md): which DOIs in the Retraction Watch database are
not registered DOIs at all, and what went wrong with them?

For every row of the Retraction Watch CSV (any RetractionNature) and both DOI fields
(OriginalPaperDOI = paper side "O", RetractionDOI = notice side "N"), the script parses the field,
and asks doi.org whether each distinct DOI exists and which registration agency (RA) holds it
(doi.org/doiRA, batched; doi.org/api/handles for single DOIs). Status per distinct (side, DOI):

  registered       doi.org knows it (RA recorded: Crossref, mEDRA, DataCite, ...)
  not_exist        well-formed, but doi.org says the DOI does not exist
  invalid          doi.org calls it an invalid DOI
  invalid_syntax   the field is not a DOI after removing URL/doi: prefixes (not asked)
  unknown          the lookup failed

For every unregistered DOI the script then tries to find the DOI that was meant:
  cleanup     a mechanical clean-up (URL fragment, query, trailing punctuation, URL tail such as
              /full or .pdf, HTML entities, %-escapes, stray spaces, a DOI embedded in text)
              gives a registered DOI
  repaired    a Crossref bibliographic search for RW's Title returns, in its top 5, exactly one
              DOI that is near the unregistered one (truncated by <= 3 characters, <= 3 extra
              characters, same suffix under another prefix, or edit distance <= 2) and whose title
              shares >= 50% of its words with RW's Title
  ambiguous   more than one such DOI
  unrepaired  none
  no_basis / not_searched / search_failed   no usable title / search cap reached / search failed

No API keys. Sources: gitlab.com/crossref/retraction-watch-data (CSV), doi.org, api.crossref.org.
Usage: python rw_doi_registration_census.py --out-dir /out
"""
import argparse
import collections
import csv
import datetime
import hashlib
import html
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
UA = "rw-doi-registration-census/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
DOIRA = "https://doi.org/doiRA/"
HANDLE = "https://doi.org/api/handles/"
CROSSREF = "https://api.crossref.org/works"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-14.md"
PLAN_MARK = b"Pre-registration 14"
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
RA_BATCH = 25
GAP = 0.3
SEARCH_CAP = 4000
GRADE_N = 20
RECENT_DAYS = 60
MIN_JACCARD = 0.5
NEEDED = ("Record ID", "Title", "Journal", "Publisher", "RetractionDate", "RetractionDOI",
          "OriginalPaperDOI", "RetractionNature")
NONE_VALUES = {"", "unavailable", "0", "n/a", "na", "none", "-", "null", "nan"}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
EMBED_RE = re.compile(r"10\.\d{4,9}/\S+")
MULTI_RE = re.compile(r"10\.\d{4,9}/")
BATCH_SAFE = re.compile(r"^10\.\d{4,9}/[a-z0-9._\-/():]+$")
URL_TAILS = ("/full/html", "/fulltext", "/abstract", "/full", "/epdf", "/pdf", ".pdf", "/meta")
UNREG = ("not_exist", "invalid", "invalid_syntax")
DONE = ("cleanup", "repaired", "ambiguous", "unrepaired", "no_basis")
FIXED = ("cleanup", "repaired")
# Read by hand before this plan (audit 11, GRADING-11.md; doi.org checked 2026-11-11), gate G3.
CONTROLS = [
    ("10.1177/014616720026200", {"status": "not_exist"}),
    ("10.18388/abp.2018_6398", {"status": "not_exist"}),
    ("10.1080/09645292.2010.545518#.us5z4lssxk0",
     {"repair": "cleanup", "fix": "10.1080/09645292.2010.545518"}),
    ("10.26355/eurrev_202101_24355", {"status": "registered", "ra": "mEDRA"}),
]
# Descriptive instrument check C1 (not a gate): the title search should find these repairs.
C1 = [("10.1177/014616720026200", "10.1177/0146167200262008"),
      ("10.18388/abp.2018_6398", "10.18388/abp.2023_6398")]
csv.field_size_limit(1 << 24)


# ---------------------------------------------------------------- pure helpers
def ascii_fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch if ord(ch) < 128 else ("" if unicodedata.combining(ch) else " ") for ch in s)


def norm_doi(d):
    """Lower case, URL and doi: prefixes removed. Trailing punctuation is KEPT (it is data here)."""
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/",
              "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip()


def parse_doi_field(raw):
    """(doi, syntax, multi): syntax is 'none' (placeholder), 'ok' or 'malformed'. A field holding
    two or more DOIs is cut to the first one (multi=True)."""
    s = str(raw if raw is not None else "").strip()
    if s.lower() in NONE_VALUES:
        return "", "none", False
    starts = [m.start() for m in MULTI_RE.finditer(s.lower())]
    multi = len(starts) >= 2
    if multi:
        s = re.sub(r"[\s;,]+$", "", s[:starts[1]])
    d = norm_doi(s)
    return d, ("ok" if DOI_RE.match(d) else "malformed"), multi


def parse_date(s):
    """'YYYY-MM-DD' from RW's 'm/d/yyyy H:MM' (or ISO) date, else ''."""
    s = str(s or "")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(3)), int(m.group(1)), int(m.group(2)))
    return ""


def days_before(day, n):
    return (datetime.date.fromisoformat(day) - datetime.timedelta(days=n)).isoformat()


def words(s):
    s = ascii_fold(s).lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\b(retracted|retraction|notice of|withdrawn)\b", " ", s)
    return {w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 2}


def jaccard(a, b):
    A, B = words(a), words(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def sha_key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def share(num, den):
    return round(num / den, 4) if den else None


def lev(a, b, cap=3):
    """Levenshtein distance, or cap + 1 if it is larger than cap."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        best = i
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if cur[j] < best:
                best = cur[j]
        if best > cap:
            return cap + 1
        prev = cur
    return min(prev[-1], cap + 1)


def cleanups(d):
    """Registered-DOI candidates from mechanical clean-ups of d, in the order tried."""
    out = []

    def add(x):
        x = x.strip()
        if x and x != d and x not in out and DOI_RE.match(x):
            out.append(x)

    x = d
    if not x.startswith("10."):
        m = EMBED_RE.search(x)
        if not m:
            return out
        x = m.group(0)
        add(x)
    y = html.unescape(x)
    if y != x:
        x = y
        add(x)
    if "%" in x:
        y = urllib.parse.unquote(x)
        if y != x:
            x = y
            add(x)
    if re.search(r"\s", x):
        add(re.sub(r"\s+", "", x))
        x = x.split()[0]
        add(x)
    for ch in "#?":
        k = x.find(ch)
        if 0 < k < len(x) - 1:
            x = x[:k]
            add(x)
    for t in URL_TAILS:
        if x.endswith(t):
            x = x[:-len(t)]
            add(x)
            break
    y = x.rstrip(".,;:'\"")
    while y.endswith(")") and y.count(")") > y.count("("):
        y = y[:-1].rstrip(".,;:")
    while y.endswith("]") and y.count("]") > y.count("["):
        y = y[:-1].rstrip(".,;:")
    if y != x:
        add(y)
    return out


def relation(bad, good):
    """How registered DOI `good` relates to unregistered `bad`, or '' if they are not near."""
    if not bad or not good or bad == good:
        return ""
    if good.startswith(bad) and len(good) - len(bad) <= 3:
        return "truncated"
    if bad.startswith(good) and len(bad) - len(good) <= 3:
        return "extra_chars"
    pb, _, sb = bad.partition("/")
    pg, _, sg = good.partition("/")
    if sb and sb == sg and pb != pg:
        return "prefix_swap"
    if lev(bad, good, 2) <= 2:
        return "typo"
    return ""


def pick(bad, items, rw_title, exclude=()):
    """('repaired' | 'ambiguous' | 'unrepaired', hits) from search items [(doi, title)].
    hits: [(doi, relation, jaccard, title)]."""
    hits, seen = [], set()
    for g, t in items or []:
        if not g or g == bad or g in exclude or g in seen:
            continue
        seen.add(g)
        rel = relation(bad, g)
        if not rel:
            continue
        j = jaccard(rw_title, t)
        if j < MIN_JACCARD:
            continue
        hits.append((g, rel, j, t))
    if len(hits) == 1:
        return "repaired", hits
    if hits:
        return "ambiguous", hits
    return "unrepaired", []


STATS = collections.Counter()


def ra_parse(batch, obj):
    """{doi: (status, ra)} from a doiRA response for `batch`, or None if it cannot be used."""
    if not isinstance(obj, list) or not all(isinstance(r, dict) for r in obj):
        return None
    by = {str(r.get("DOI") or "").strip().lower(): r for r in obj}
    if all(d in by for d in batch):
        pairs = [(d, by[d]) for d in batch]
    elif len(obj) == len(batch):
        STATS["ra_positional"] += 1
        pairs = list(zip(batch, obj))
    else:
        return None
    out = {}
    for d, r in pairs:
        ra = str(r.get("RA") or "").strip()
        if ra:
            out[d] = ("registered", ra)
            continue
        s = str(r.get("status") or "").strip().lower()
        if "not exist" in s:
            out[d] = ("not_exist", "")
        elif "invalid" in s:
            out[d] = ("invalid", "")
        else:
            out[d] = ("unknown", s[:40])
    return out


def rw_entries(lines):
    """{(side, doi): entry} for every RW row-side with a DOI field that is not a placeholder."""
    entries, st = {}, collections.Counter()
    header_ok = None
    for row in csv.DictReader(lines):
        if header_ok is None:
            header_ok = all(k in row for k in NEEDED)
        st["rows"] += 1
        rid = str(row.get("Record ID") or "").strip()
        rdate = parse_date(row.get("RetractionDate"))
        o = parse_doi_field(row.get("OriginalPaperDOI"))
        n = parse_doi_field(row.get("RetractionDOI"))
        if o[1] == "none" and n[1] == "none":
            st["rows_no_doi"] += 1
        if o[1] == "ok" and n[1] == "ok" and o[0] == n[0]:
            st["rows_same_doi"] += 1
        for side, (d, syn, multi), other, key in (("O", o, n[0], "OriginalPaperDOI"),
                                                  ("N", n, o[0], "RetractionDOI")):
            st["%s_%s" % (side, syn)] += 1
            if multi:
                st["%s_multi" % side] += 1
            if syn == "none":
                continue
            e = entries.get((side, d))
            if e is None:
                e = entries[(side, d)] = {
                    "side": side, "doi": d, "syntax": syn,
                    "raw": str(row.get(key) or "").strip()[:200], "n_rows": 0, "record_ids": [],
                    "nature": str(row.get("RetractionNature") or "").strip(),
                    "title": str(row.get("Title") or "").strip()[:200],
                    "journal": str(row.get("Journal") or "").strip()[:80],
                    "publisher": str(row.get("Publisher") or "").strip()[:80],
                    "rdate": rdate, "other_doi": other, "status": "", "ra": "", "repair": "",
                    "repair_class": "", "fix": "", "fix_title": "", "title_jaccard": "",
                    "candidates": ""}
            e["n_rows"] += 1
            if len(e["record_ids"]) < 10:
                e["record_ids"].append(rid)
            if rdate > e["rdate"]:
                e["rdate"] = rdate
    st["header_ok"] = 1 if header_ok else 0
    return entries, st


def check_controls(entries):
    by = {}
    for e in entries.values():
        by.setdefault(e["doi"], []).append(e)
    out = {}
    for doi, want in CONTROLS:
        es = by.get(doi, [])
        got = {k: (es[0].get(k) if es else None) for k in want}
        ok = bool(es) and all(str(got[k]).lower() == str(v).lower() for k, v in want.items())
        out[doi] = {"got": got, "ok": ok}
    return out


def grade(entries, today, gates):
    """Predictions P1-P6 of PREREG-14.md from a list of entries (status, ra, repair, ...)."""
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    def side_rate(side):
        xs = [e for e in entries if e["side"] == side and e["status"] != "unknown"]
        return sum(1 for e in xs if e["status"] in UNREG), len(xs)

    uo, no = side_rate("O")
    un, nn = side_rate("N")
    po, pn = share(uo, no), share(un, nn)
    put("P1", po, po is not None and 0.003 <= po <= 0.03,
        "unregistered share of distinct paper-side DOIs in 0.3%-3%")
    put("P2", [pn, po], pn is not None and po is not None and pn >= po,
        "notice-side unregistered share >= paper-side share")
    cut = days_before(today, RECENT_DAYS)
    ns = [e for e in entries if e["side"] == "N" and e["status"] != "unknown" and e["rdate"]]
    rec = [e for e in ns if e["rdate"] >= cut]
    old = [e for e in ns if e["rdate"] < cut]
    if len(rec) >= 200 and old:
        r1 = share(sum(1 for e in rec if e["status"] in UNREG), len(rec))
        r0 = share(sum(1 for e in old if e["status"] in UNREG), len(old))
        ok = r1 >= 3 * r0 if r0 > 0 else r1 > 0
        put("P3", [r1, r0], ok,
            "notice DOIs dated in the last %d days: unregistered share >= 3x older ones" % RECENT_DAYS)
    else:
        put("P3", len(rec), None, "inconclusive: fewer than 200 recent notice DOIs")
    pu = [e for e in entries if e["side"] == "O" and e["status"] in UNREG]
    done = [e for e in pu if e["repair"] in DONE]
    fixed = [e for e in done if e["repair"] in FIXED]
    if len(done) >= 30:
        v = share(len(fixed), len(done))
        put("P4", v, v >= 0.4, ">= 40% of processed unregistered paper DOIs get a unique repair")
    else:
        put("P4", len(done), None, "inconclusive: fewer than 30 processed")
    cls = collections.Counter(e["repair_class"] for e in fixed)
    if sum(cls.values()) >= 10:
        top = cls.most_common()
        ok = top[0][0] == "truncated" and (len(top) == 1 or top[0][1] > top[1][1])
        put("P5", dict(cls), ok, "truncation is the single most common repair class (paper side)")
    else:
        put("P5", dict(cls), None, "inconclusive: fewer than 10 paper-side repairs")
    reg = [e for e in entries if e["side"] == "O" and e["status"] == "registered"
           and e["ra"] not in ("", "?")]
    other = sum(1 for e in reg if e["ra"].lower() != "crossref")
    v = share(other, len(reg))
    put("P6", v, v is not None and v >= 0.005,
        ">= 0.5% of registered paper DOIs are held by an agency other than Crossref")
    if not all(g.get("ok") for g in gates.values()):
        for k in res:
            res[k]["note"] += " (a gate failed: reported descriptively, not graded)"
    return res


# ---------------------------------------------------------------- network
_LAST = {}


def http(url, data=None, tries=6, timeout=120, gap=0.4, host="x"):
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
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None


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


def load_rw(tmp):
    for u in RW_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            with open(tmp, encoding="utf-8-sig", errors="replace", newline="") as f:
                entries, st = rw_entries(f)
            if st["header_ok"]:
                return entries, st, u
            STATS["rw_badheader"] += 1
        except Exception as e:
            STATS["rw_error"] += 1
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return {}, collections.Counter(), ""


def lookup_single(d):
    if "," not in d:
        st, body = http(DOIRA + urllib.parse.quote(d, safe="/()"), host="doi", gap=GAP)
        got = ra_parse([d], jload(body)) if st == 200 else None
        if got and got[d][0] != "unknown":
            return got[d]
    st, body = http(HANDLE + urllib.parse.quote(d, safe="/"), host="doi", gap=GAP)
    if st == 404:
        return ("not_exist", "")
    if st == 400:
        return ("invalid", "")
    obj = jload(body) if st == 200 else None
    if isinstance(obj, dict):
        rc = obj.get("responseCode")
        if rc == 1:
            return ("registered", "?")
        if rc == 100:
            return ("not_exist", "")
    return ("unknown", str(st))


def lookup(dois, res):
    """Fill res {doi: (status, ra)} for every DOI not already in it. Returns failed batches."""
    todo = [d for d in dois if d not in res]
    batch_ok = [d for d in todo if BATCH_SAFE.match(d)]
    singles = [d for d in todo if not BATCH_SAFE.match(d)]
    failed, i, size, n_b = 0, 0, RA_BATCH, 0
    while i < len(batch_ok):
        b = batch_ok[i:i + size]
        st, body = http(DOIRA + ",".join(b), host="doi", gap=GAP)
        got = ra_parse(b, jload(body)) if st == 200 else None
        if got is None:
            failed += 1
            if size > 5:
                size = max(5, size // 2)
                continue
            singles.extend(b)
        else:
            res.update(got)
        i += len(b)
        n_b += 1
        if n_b % 400 == 0:
            print("doiRA %d/%d" % (i, len(batch_ok)), flush=True)
    for k, d in enumerate(singles):
        res[d] = lookup_single(d)
        if (k + 1) % 200 == 0:
            print("singles %d/%d" % (k + 1, len(singles)), flush=True)
    return failed


def search(title):
    """[(doi, title)] from Crossref's top 5 for RW's title, or None if the search failed."""
    q = re.sub(r"\s+", " ", ascii_fold(title)).strip()[:250]
    url = ("%s?query.bibliographic=%s&rows=5&select=DOI,title&mailto=%s"
           % (CROSSREF, urllib.parse.quote(q), MAILTO))
    st, body = http(url, host="crossref", gap=0.3)
    obj = jload(body) if st == 200 else None
    msg = obj.get("message") if isinstance(obj, dict) else None
    if not isinstance(msg, dict):
        return None
    out = []
    for it in msg.get("items") or []:
        t = it.get("title")
        t = (t[0] if t else "") if isinstance(t, list) else str(t or "")
        out.append((norm_doi(it.get("DOI")), str(t)[:300]))
    return out


# ---------------------------------------------------------------- main
FIELDS = ["side", "doi", "raw", "syntax", "status", "ra", "n_rows", "record_ids", "nature",
          "rdate", "title", "journal", "publisher", "other_doi", "repair", "repair_class", "fix",
          "fix_title", "title_jaccard", "candidates", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for e in rows:
            r = dict(e)
            r["record_ids"] = ";".join(e["record_ids"])
            r["title"] = e["title"][:150]
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=120)
    ap.add_argument("--search-cap", type=int, default=SEARCH_CAP)
    ap.add_argument("--tmp", default="/tmp/retraction_watch.csv")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    s = {"preregistered": PLAN, "started": now()}
    s["plan_live_at"] = wait_for_plan(a.wait_min)
    if not s["plan_live_at"]:
        s["error"] = "plan not live; nothing run"
        with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
        return 0
    s["data_started"] = now()

    entries, rst, src = load_rw(a.tmp)
    s["rw_source"], s["rw_counts"] = src, dict(rst)
    print("RW %d rows, %d (side, DOI) entries from %s" % (rst["rows"], len(entries), src), flush=True)

    res = {}
    asked = sorted({e["doi"] for e in entries.values() if e["syntax"] == "ok"})
    failed = lookup(asked, res)
    for e in entries.values():
        if e["syntax"] != "ok":
            e["status"] = "invalid_syntax"
        else:
            e["status"], e["ra"] = res.get(e["doi"], ("unknown", ""))
    print("lookup done: %s, %.0fs" % (dict(collections.Counter(e["status"] for e in entries.values())),
                                      time.monotonic() - t0), flush=True)

    unreg = sorted((e for e in entries.values() if e["status"] in UNREG),
                   key=lambda e: (e["side"] != "O", sha_key("a14s", e["side"], e["doi"])))
    cl = {e["doi"]: cleanups(e["doi"]) for e in unreg}
    failed_c = lookup(sorted({c for v in cl.values() for c in v}), res)
    for e in unreg:
        for c in cl[e["doi"]]:
            if res.get(c, ("",))[0] == "registered":
                e.update(repair="cleanup", repair_class="cleanup", fix=c)
                break
    searched = 0
    for e in unreg:
        if e["repair"]:
            continue
        if len(words(e["title"])) < 3:
            e["repair"] = "no_basis"
            continue
        if searched >= a.search_cap:
            e["repair"] = "not_searched"
            continue
        items = search(e["title"])
        searched += 1
        if items is None:
            e["repair"] = "search_failed"
            continue
        exclude = {e["other_doi"]} if e["other_doi"] else set()
        stt, hits = pick(e["doi"], items, e["title"], exclude)
        e["repair"] = stt
        if stt == "repaired":
            g, rel, j, t = hits[0]
            e.update(repair_class=rel, fix=g, fix_title=t[:150], title_jaccard=round(j, 3))
        elif stt == "ambiguous":
            e["candidates"] = ";".join("%s(%s)" % (h[0], h[1]) for h in hits)
        if searched % 250 == 0:
            print("searched %d" % searched, flush=True)

    ev = list(entries.values())
    n_unknown = sum(1 for e in ev if e["status"] == "unknown")
    ctl = check_controls(entries)
    gates = {
        "G1_rw_rows": {"value": rst["rows"], "ok": rst["rows"] >= 60000 and bool(rst["header_ok"])},
        "G2_lookup_unknown": {"value": [n_unknown, len(asked), failed, failed_c],
                              "ok": n_unknown <= 0.02 * max(len(asked), 1)},
        "G3_controls": {"value": ctl, "ok": all(v["ok"] for v in ctl.values())},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
    }
    preds = grade(ev, s["data_started"][:10], gates)
    by_doi = {}
    for e in ev:
        by_doi.setdefault(e["doi"], e)
    c1 = {bad: {"repair": (by_doi.get(bad) or {}).get("repair"),
                "fix": (by_doi.get(bad) or {}).get("fix"), "expected": good,
                "ok": (by_doi.get(bad) or {}).get("fix") == good} for bad, good in C1}

    un = [e for e in ev if e["status"] in UNREG]
    un.sort(key=lambda e: (e["side"], e["publisher"], e["doi"]))
    write_csv(os.path.join(a.out_dir, "unregistered.csv"), un)
    write_csv(os.path.join(a.out_dir, "non_crossref_ra.csv"),
              sorted((e for e in ev if e["status"] == "registered" and e["ra"].lower() != "crossref"),
                     key=lambda e: (e["side"], e["ra"], e["doi"])))
    po = [e for e in un if e["side"] == "O"]
    write_csv(os.path.join(a.out_dir, "grade20_repaired_paper.csv"),
              sorted((e for e in po if e["repair"] in FIXED),
                     key=lambda e: sha_key("a14g", e["doi"]))[:GRADE_N])
    write_csv(os.path.join(a.out_dir, "grade20_unrepaired_paper.csv"),
              sorted((e for e in po if e["repair"] == "unrepaired"),
                     key=lambda e: sha_key("a14u", e["doi"]))[:GRADE_N])

    def by_side(f):
        return {sd: f([e for e in ev if e["side"] == sd]) for sd in ("O", "N")}

    s.update({
        "n_entries": len(ev), "n_dois_asked": len(asked), "n_unknown": n_unknown,
        "doira_failed_batches": failed, "cleanup_failed_batches": failed_c, "searched": searched,
        "status": by_side(lambda xs: dict(collections.Counter(e["status"] for e in xs))),
        "ra": by_side(lambda xs: dict(collections.Counter(e["ra"] for e in xs
                                                          if e["status"] == "registered"))),
        "repair": by_side(lambda xs: dict(collections.Counter(e["repair"] for e in xs
                                                              if e["status"] in UNREG))),
        "repair_class": by_side(lambda xs: dict(collections.Counter(
            e["repair_class"] for e in xs if e["repair"] in FIXED))),
        "unregistered_rows": by_side(lambda xs: sum(e["n_rows"] for e in xs
                                                    if e["status"] in UNREG)),
        "unregistered_by_publisher": by_side(lambda xs: collections.Counter(
            e["publisher"] for e in xs if e["status"] in UNREG).most_common(25)),
        "unregistered_by_year": by_side(lambda xs: dict(sorted(collections.Counter(
            e["rdate"][:4] for e in xs if e["status"] in UNREG).items()))),
        "entries_by_year": by_side(lambda xs: dict(sorted(collections.Counter(
            e["rdate"][:4] for e in xs).items()))),
        "malformed_examples": [e["raw"] for e in ev if e["syntax"] == "malformed"][:30],
        "c1_title_search_controls": c1,
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()),
        "predictions": preds, "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps({"status": s["status"], "repair": s["repair"], "gates_ok": s["all_gates_ok"],
                      "predictions": {k: v["held"] for k, v in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
