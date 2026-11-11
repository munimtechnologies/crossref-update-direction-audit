#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name; no human has reviewed it.
"""Audit 16 (pre-registered in PREREG-16.md): Cochrane withdrawals and Retraction Watch.

Since mid-2019 Cochrane says it withdraws a review only in exceptional circumstances (serious
error, misconduct, a serious conflict-of-interest breach), in line with COPE's retraction
guidance. This script asks whether the Retraction Watch database lists the Cochrane reviews
withdrawn since then, compared with those withdrawn before, and why each recent one was withdrawn.

1. Walk Crossref for every notice in the Cochrane Database of Systematic Reviews (ISSN 1465-1858)
   with an `update-to` of type `withdrawal` or `retraction`. Keep one event per withdrawn item
   (publisher-deposited links only; the earliest notice date). Retraction Watch links that
   Crossref shows (source `retraction-watch`) are kept as a separate flag.
2. Read the Retraction Watch CSV (Crossref's GitLab copy) and index its Cochrane rows by the
   retracted item's DOI and by the review's CD number.
3. For each withdrawn review version (DOI ending .pubN) withdrawn on or after 2019-07-01, read
   the notice in Europe PMC: publication types and the sentence that says why it was withdrawn.

No API keys. raw.githubusercontent.com, api.crossref.org, gitlab.com, www.ebi.ac.uk.
Usage: python cochrane_withdrawal_rw_audit.py --out-dir /out
"""
import argparse
import collections
import csv
import datetime
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
UA = "cochrane-withdrawal-rw-audit/1.0 (MV2, Munim, Inc.; mailto:mv2@munimtech.com)"
CROSSREF = "https://api.crossref.org/works"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "PREREG-16.md"
PLAN_MARK = b"Pre-registration 16"
RW_URLS = [
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
    "https://api.labs.crossref.org/data/retractionwatch?mailto=" + MAILTO,
]
ISSN = "1465-1858"
PREFIX = "10.1002/14651858."
POLICY = datetime.date(2019, 7, 1)
POLICY_ALT = datetime.date(2019, 8, 19)
PRE_START = datetime.date(2009, 1, 1)
NEAR_DAYS = 365
RETRACTIVE = {"withdrawal", "retraction", "partial_retraction", "removal"}
NOT_RETRACTION = ("correction", "expression of concern", "reinstatement")
# Gate G3: Crossref already shows a Retraction Watch link for both (read by hand 2026-11-11).
CONTROLS = ["10.1002/14651858.cd011313.pub3", "10.1002/14651858.cd006581.pub2"]
NEEDED = ("Record ID", "Journal", "RetractionDate", "RetractionDOI", "OriginalPaperDOI",
          "RetractionNature")
csv.field_size_limit(1 << 24)

CD = re.compile(r"14651858\.((?:cd|mr)\d{6})", re.I)
PUB = re.compile(r"\.pub\d+$")
INTEGRITY = re.compile(
    r"\berrors?\b|conflicts? of interest|commercial sponsorship|\bbreach|misconduct|fabricat|"
    r"falsif|plagiar|methodological (?:problems|flaws|concerns|issues)|\bretracted\b|"
    r"not (?:be )?reliable|unreliable|integrity", re.I)
CURRENCY = re.compile(
    r"out[ -]of[ -]date|supersede|supercede|not been updated|"
    r"no longer (?:current|relevant|up[ -]to[ -]date)|split into|been split|replaced by|"
    r"recent evidence|new studies|timelines", re.I)


# ---------------------------------------------------------------- pure helpers
def norm_doi(d):
    d = str(d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/",
              "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip().rstrip(".")


def dois_in(s):
    out = []
    for part in re.split(r"[;\s]+", str(s or "")):
        d = norm_doi(part)
        if re.match(r"^10\.\d{4,9}/\S+$", d):
            out.append(d)
    return out


def cd_id(doi):
    m = CD.search(str(doi or ""))
    return m.group(1).lower() if m else ""


def target_kind(doi):
    """'review' for a CDSR version DOI ending .pubN, 'bare' for the bare CD number (usually the
    protocol), 'other' for anything else."""
    d = norm_doi(doi)
    if not d.startswith(PREFIX) or not cd_id(d):
        return "other"
    return "review" if PUB.search(d) else "bare"


def date_from_parts(dp):
    """datetime.date from Crossref {'date-parts': [[y, m, d]]} (missing month/day -> 1)."""
    try:
        p = (dp or {}).get("date-parts")[0]
        y = int(p[0])
        m = int(p[1]) if len(p) > 1 and p[1] else 1
        d = int(p[2]) if len(p) > 2 and p[2] else 1
        return datetime.date(y, m, d)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def parse_rw_date(s):
    """RW RetractionDate ('11/30/2021 0:00' or '2021-11-30') -> date, else None."""
    s = str(s or "").strip()
    try:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            return datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return None


def period(d):
    if d is None:
        return "undated"
    if d >= POLICY:
        return "post"
    if d >= PRE_START:
        return "pre"
    return "early"


def reason_sentence(abstract):
    """The sentence that says the review was withdrawn, plus the two after it (tags removed)."""
    t = re.sub(r"<[^>]+>", " ", html.unescape(str(abstract or "")))
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    sents = re.split(r"(?<=[.!?])\s+", t)
    for i, s in enumerate(sents):
        if re.search(r"withdr[ae]w", s, re.I):
            return " ".join(sents[i:i + 3])[:600]
    return t[:600]


def reason_class(text):
    """'integrity' (error, misconduct, conflict of interest, retracted data), 'currency' (out of
    date, superseded, split, not updated), 'other', or 'no_text'. Integrity wins if both match."""
    t = str(text or "")
    if not t.strip():
        return "no_text"
    if INTEGRITY.search(t):
        return "integrity"
    if CURRENCY.search(t):
        return "currency"
    return "other"


def events_from_items(items):
    """One dict per update-to entry of each Crossref notice item."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        notice = norm_doi(it.get("DOI"))
        for u in it.get("update-to") or []:
            if not isinstance(u, dict):
                continue
            out.append({"notice": notice, "target": norm_doi(u.get("DOI")),
                        "type": str(u.get("type") or "").strip().lower(),
                        "source": str(u.get("source") or "").strip().lower(),
                        "record_id": str(u.get("record-id") or ""),
                        "date": date_from_parts(u.get("updated")) or date_from_parts(it.get("issued"))})
    return out


def collapse(raw):
    """(one event per withdrawn CDSR item from publisher links, set of targets that Crossref
    shows a Retraction Watch link for)."""
    xr_rw = set()
    by_t = {}
    for e in raw:
        if e["source"] == "retraction-watch":
            xr_rw.add(e["target"])
            continue
        if e["type"] not in RETRACTIVE or not e["target"] or e["target"] == e["notice"]:
            continue
        if not e["target"].startswith(PREFIX):
            continue
        cur = by_t.get(e["target"])
        if cur is None:
            by_t[e["target"]] = dict(e, kind=target_kind(e["target"]), cd=cd_id(e["target"]),
                                     notices={e["notice"]}, types={e["type"]})
            continue
        cur["notices"].add(e["notice"])
        cur["types"].add(e["type"])
        if e["date"] and (cur["date"] is None or e["date"] < cur["date"]):
            cur["date"] = e["date"]
            cur["notice"] = e["notice"]
    out = []
    for t in sorted(by_t):
        d = by_t[t]
        d["notices"] = ";".join(sorted(d["notices"]))
        d["types"] = ";".join(sorted(d["types"]))
        out.append(d)
    return out, xr_rw


def rw_index(lines):
    """Cochrane rows of the RW CSV indexed by retracted-item DOI and by CD number."""
    by_doi, by_cd = collections.defaultdict(list), collections.defaultdict(list)
    st = collections.Counter()
    header_ok = None
    for row in csv.DictReader(lines):
        if header_ok is None:
            header_ok = all(k in row for k in NEEDED)
        st["rows"] += 1
        coch = [d for d in dois_in(row.get("OriginalPaperDOI")) if d.startswith(PREFIX)]
        if not coch and "cochrane" not in str(row.get("Journal") or "").lower():
            continue
        st["cochrane_rows"] += 1
        if not coch:
            st["cochrane_rows_no_cdsr_doi"] += 1
        r = {"id": str(row.get("Record ID") or "").strip(),
             "date": parse_rw_date(row.get("RetractionDate")),
             "nature": str(row.get("RetractionNature") or "").strip(),
             "reason": str(row.get("Reason") or "").strip()[:200],
             "n_doi": ";".join(dois_in(row.get("RetractionDOI")))}
        for d in coch:
            by_doi[d].append(r)
            c = cd_id(d)
            if c:
                by_cd[c].append(r)
    st["header_ok"] = 1 if header_ok else 0
    return dict(by_doi), dict(by_cd), st


def rw_ok(r):
    n = r["nature"].lower()
    return not any(x in n for x in NOT_RETRACTION)


def match(ev, by_doi, by_cd):
    """rw_exact: RW lists this DOI; rw_near: RW lists this DOI, or another version of the same CD
    number with an RW date within 365 days of the notice (or either date missing)."""
    exact = [r for r in by_doi.get(ev["target"], []) if rw_ok(r)]
    near = []
    for r in by_cd.get(ev.get("cd") or "", []):
        if not rw_ok(r):
            continue
        if r["date"] is None or ev.get("date") is None or abs((r["date"] - ev["date"]).days) <= NEAR_DAYS:
            near.append(r)
    hit = exact or near
    return {"rw_exact": bool(exact), "rw_near": bool(exact or near),
            "rw_ids": ";".join(sorted({r["id"] for r in exact + near})),
            "rw_reason": hit[0]["reason"] if hit else "",
            "rw_nature": hit[0]["nature"] if hit else ""}


def parse_epmc(obj, doi):
    """Europe PMC search response -> {'found', 'pmid', 'pubtypes', 'abstract'} for doi."""
    for r in ((obj or {}).get("resultList") or {}).get("result") or []:
        if isinstance(r, dict) and norm_doi(r.get("doi")) == doi:
            pt = (r.get("pubTypeList") or {}).get("pubType") or []
            if isinstance(pt, str):
                pt = [pt]
            return {"found": True, "pmid": str(r.get("pmid") or ""),
                    "pubtypes": ";".join(str(x) for x in pt),
                    "abstract": str(r.get("abstractText") or "")}
    return {"found": False, "pmid": "", "pubtypes": "", "abstract": ""}


def share(num, den):
    return round(num / den, 4) if den else None


# ---------------------------------------------------------------- grading
def grade(events, post_rev, gates):
    """Predictions P1-P6 of PREREG-16.md."""
    res = {}

    def put(k, value, ok, note):
        res[k] = {"value": value, "held": ok, "note": note}

    def cov(rows, key):
        return share(sum(1 for e in rows if e.get(key)), len(rows))

    n = len(post_rev)
    put("P1", n, 15 <= n <= 40, "withdrawn CDSR review versions with a notice on/after 2019-07-01 in 15-40")
    if n >= 10:
        v = cov(post_rev, "rw_exact")
        put("P2", v, v <= 0.2, "RW lists the exact DOI for <= 20% of them")
        v = cov(post_rev, "rw_near")
        put("P3", v, v <= 0.3, "RW lists the DOI or a same-CD version within 365 days for <= 30%")
    else:
        put("P2", n, None, "inconclusive: fewer than 10 post-policy review withdrawals")
        put("P3", n, None, "inconclusive: fewer than 10 post-policy review withdrawals")
    pre_rev = [e for e in events if e.get("period") == "pre" and e.get("kind") == "review"]
    if len(pre_rev) >= 30:
        v = cov(pre_rev, "rw_exact")
        put("P4", v, v >= 0.4, "RW lists the exact DOI for >= 40% of 2009-2019/06 review withdrawals")
    else:
        put("P4", len(pre_rev), None, "inconclusive: fewer than 30 pre-policy review withdrawals")
    post_bare = [e for e in events if e.get("period") == "post" and e.get("kind") == "bare"]
    if len(post_bare) >= 30:
        v = cov(post_bare, "rw_near")
        put("P5", v, v <= 0.05, "RW lists <= 5% of post-policy bare-DOI (protocol) withdrawals")
    else:
        put("P5", len(post_bare), None, "inconclusive: fewer than 30 post-policy bare-DOI withdrawals")
    found = [e for e in post_rev if e.get("epmc_found")]
    ni = sum(1 for e in found if e.get("reason_class") == "integrity")
    nc = sum(1 for e in found if e.get("reason_class") == "currency")
    if len(found) >= 6:
        put("P6", [ni, nc, len(found)], ni >= 3 and nc >= 3,
            ">= 3 integrity and >= 3 currency reasons among post-policy review notices in Europe PMC")
    else:
        put("P6", len(found), None, "inconclusive: fewer than 6 notices found in Europe PMC")
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


def walk(update_type):
    """(items, total-results, failed requests) for CDSR notices with this update type."""
    items, cursor, total, fails = [], "*", None, 0
    while True:
        url = ("%s?filter=issn:%s,update-type:%s&rows=1000&cursor=%s"
               "&select=DOI,title,issued,update-to&mailto=%s"
               % (CROSSREF, ISSN, update_type, urllib.parse.quote(cursor, safe=""), MAILTO))
        st, body = http(url, host="crossref", gap=1.0)
        msg = (jload(body) or {}).get("message") if st == 200 else None
        if not isinstance(msg, dict):
            fails += 1
            if fails > 3:
                break
            continue
        got = msg.get("items") or []
        items.extend(got)
        total = msg.get("total-results")
        nxt = msg.get("next-cursor")
        if not got or not nxt or len(items) >= (total or 0):
            break
        cursor = nxt
    return items, total, fails


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
                by_doi, by_cd, st = rw_index(f)
            if st["header_ok"]:
                return by_doi, by_cd, st, u
            STATS["rw_badheader"] += 1
        except Exception as e:
            STATS["rw_error"] += 1
            print("RW download failed from %s: %s" % (u, e), file=sys.stderr, flush=True)
    return {}, {}, collections.Counter(), ""


def epmc_lookup(doi):
    q = 'DOI:"%s"' % doi
    url = "%s?query=%s&resultType=core&format=json&pageSize=5" % (EPMC, urllib.parse.quote(q))
    st, body = http(url, host="epmc", gap=0.3)
    obj = jload(body) if st == 200 else None
    if obj is None:
        return None
    return parse_epmc(obj, doi)


# ---------------------------------------------------------------- main
FIELDS = ["target", "kind", "cd", "date", "period", "notice", "notices", "types", "rw_exact",
          "rw_near", "rw_ids", "rw_nature", "rw_reason", "crossref_rw", "epmc_found", "pmid",
          "pubtypes", "retraction_pubtype", "reason_class", "reason", "grade", "note"]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=120)
    ap.add_argument("--tmp", default="/tmp/retraction_watch.csv")
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

    w_items, w_total, w_fail = walk("withdrawal")
    r_items, r_total, r_fail = walk("retraction")
    print("crossref: withdrawal %d/%s, retraction %d/%s" % (len(w_items), w_total, len(r_items),
                                                            r_total), flush=True)
    events, xr_rw = collapse(events_from_items(w_items) + events_from_items(r_items))

    by_doi, by_cd, rst, src = load_rw(a.tmp)
    s["rw_source"], s["rw_counts"] = src, dict(rst)
    print("RW %d rows, %d Cochrane rows from %s" % (rst["rows"], rst["cochrane_rows"], src), flush=True)

    for e in events:
        e.update(match(e, by_doi, by_cd))
        e["crossref_rw"] = e["target"] in xr_rw
        e["period"] = period(e["date"])

    post_rev = [e for e in events if e["period"] == "post" and e["kind"] == "review"]
    n_ep, n_ep_fail = 0, 0
    for e in post_rev:
        n_ep += 1
        r = epmc_lookup(e["notice"])
        if r is None:
            n_ep_fail += 1
            e.update({"epmc_found": "", "reason_class": "lookup_failed"})
            continue
        reason = reason_sentence(r["abstract"])
        e.update({"epmc_found": r["found"], "pmid": r["pmid"], "pubtypes": r["pubtypes"],
                  "retraction_pubtype": "retraction of publication" in r["pubtypes"].lower(),
                  "reason": reason, "reason_class": reason_class(reason) if r["found"] else "not_found"})

    by_t = {e["target"]: e for e in events}
    ctl = {t: by_t.get(t, {}).get("rw_exact") for t in CONTROLS}
    gates = {
        "G1_crossref": {"value": {"withdrawal": [len(w_items), w_total, w_fail],
                                  "retraction": [len(r_items), r_total, r_fail]},
                        "ok": bool(w_total) and w_total >= 1300 and len(w_items) >= 0.98 * w_total
                        and bool(r_total) and len(r_items) >= 0.98 * r_total},
        "G2_rw": {"value": [rst["rows"], rst["header_ok"]],
                  "ok": rst["rows"] >= 60000 and bool(rst["header_ok"])},
        "G3_controls": {"value": ctl, "ok": all(v is True for v in ctl.values())},
        "G4_plan_live_first": {"value": s["plan_live_at"], "ok": bool(s["plan_live_at"])},
        "G5_epmc": {"value": [n_ep_fail, n_ep], "ok": n_ep_fail <= 0.1 * max(n_ep, 1)},
    }
    preds = grade(events, post_rev, gates)

    table = collections.defaultdict(lambda: [0, 0, 0, 0])
    for e in events:
        k = "%s|%s" % (e["date"].year if e["date"] else "none", e["kind"])
        table[k][0] += 1
        table[k][1] += 1 if e["rw_exact"] else 0
        table[k][2] += 1 if e["rw_near"] else 0
        table[k][3] += 1 if e["crossref_rw"] else 0

    events.sort(key=lambda e: (str(e["date"]), e["target"]))
    write_csv(os.path.join(a.out_dir, "events.csv"), events)
    write_csv(os.path.join(a.out_dir, "post_policy_reviews.csv"), post_rev)

    s.update({
        "n_events": len(events), "kinds": dict(collections.Counter(e["kind"] for e in events)),
        "periods": dict(collections.Counter("%s|%s" % (e["period"], e["kind"]) for e in events)),
        "year_kind_n_exact_near_crossrefrw": dict(sorted(table.items())),
        "post_rev_before_2019_08_19": sum(1 for e in post_rev if e["date"] < POLICY_ALT),
        "post_rev_reason_classes": dict(collections.Counter(e.get("reason_class") for e in post_rev)),
        "post_rev_retraction_pubtype": sum(1 for e in post_rev if e.get("retraction_pubtype") is True),
        "post_rev_crossref_rw": sum(1 for e in post_rev if e["crossref_rw"]),
        "gates": gates, "all_gates_ok": all(g["ok"] for g in gates.values()), "predictions": preds,
        "http": dict(STATS), "elapsed_s": round(time.monotonic() - t0, 1),
    })
    dump()
    print(json.dumps({"n_post_rev": len(post_rev), "gates_ok": s["all_gates_ok"],
                      "predictions": {k: x["held"] for k, x in preds.items()}}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
