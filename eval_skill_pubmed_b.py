#!/usr/bin/env python3
# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""EVAL-2B: re-run EVAL-2's 40 DOIs on retraction-crosscheck 0.2.0, which should no longer count
PubMed's flag from a withdrawn correction as confirmation. See eval/EVAL-2B-PLAN.md.

The script waits until both the plan and the expected skill version are live on GitHub, records
when it saw them, then downloads the live skill, runs the repository's tests and the skill."""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

RAW = "https://raw.githubusercontent.com/munimtechnologies/crossref-update-direction-audit/main/"
PLAN = "eval/EVAL-2B-PLAN.md"
PLAN_MARK = b"EVAL-2B plan"
FILES = ["skills/retraction-crosscheck/scripts/retraction_crosscheck.py",
         "skills/retraction-crosscheck/data/known_errors.csv",
         "skills/retraction-crosscheck/SKILL.md",
         "skills/retraction-crosscheck/CHANGELOG.md",
         "test_retraction_crosscheck.py"]
SCRIPT = FILES[0]
WANT_VERSION = "0.2.0"
UA = "mv2-eval2b/1.0 (mailto:mv2@munimtech.com)"

# Same sets as EVAL-2 (eval_skill_pubmed.py), copied unchanged.
M = ["10.1016/j.cjca.2025.07.027", "10.1016/j.amjmed.2016.08.025", "10.1016/j.ejogrb.2015.07.009",
     "10.1016/j.intimp.2024.111636", "10.1016/j.wneu.2018.05.128", "10.1016/j.toxrep.2021.04.002",
     "10.1016/j.jaad.2022.12.023", "10.1016/j.jaad.2022.12.024", "10.1016/j.ijbiomac.2024.136739"]
R_RNC = ["10.1007/s11882-006-0040-5", "10.1007/s00403-006-0732-7", "10.1007/s00345-007-0190-7",
         "10.1007/s00270-008-9326-4", "10.1007/s10571-009-9449-4", "10.1007/s10709-009-9422-7",
         "10.1007/s10067-009-1354-1", "10.1007/s00268-010-0426-3", "10.1007/s10072-010-0320-7",
         "10.1007/s10067-010-1539-7", "10.1007/s10709-010-9489-1", "10.1007/s10067-010-1565-5",
         "10.1016/j.ridd.2011.03.014"]
R_C = ["10.1007/s10157-004-0307-x", "10.1007/s10488-006-0092-9", "10.1007/s11060-007-9387-2",
       "10.1016/s0039-9140(03)00007-9", "10.1111/j.1365-2559.2009.03279.x",
       "10.1007/s11832-009-0202-9", "10.1007/s00705-010-0733-x", "10.1007/978-1-60761-823-2_7",
       "10.1007/s00467-011-1882-1", "10.3892/ol.2013.1586", "10.5152/jtgga.2015.0082",
       "10.1194/jlr.m068692", "10.1016/j.jaad.2016.07.062", "10.1016/j.jdent.2017.11.011",
       "10.1016/j.tjog.2018.11.008", "10.1053/j.sult.2020.03.001", "10.24926/iip.v11i1.1662"]
R = R_RNC + R_C
U = ["10.2174/1573405620666230809105544"]
NOT_ASSESSED = {"", "not_found", "lookup_failed"}


def norm(d):
    d = (d or "").strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def index_rows(text):
    """Map normalised DOI -> {"verdict": str, "wc": bool or None} from the skill's --json output
    ({"results": [...]} or a bare list). "wc" is pubmed.flag_from_withdrawn_correction (None if
    the row has no PubMed record or no such field). Returns None if the text is not such JSON."""
    try:
        data = json.loads(text)
    except Exception:
        return None
    rows = data.get("results") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return None
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        doi = r.get("doi") or r.get("input") or ""
        if not doi:
            continue
        pm = r.get("pubmed") if isinstance(r.get("pubmed"), dict) else {}
        wc = pm.get("flag_from_withdrawn_correction")
        out[norm(str(doi))] = {"verdict": str(r.get("verdict") or r.get("status") or ""),
                               "wc": wc if isinstance(wc, bool) else None}
    return out


def grade(rows, version="", tests_exit=None):
    v = {d: (rows.get(norm(d)) or {}).get("verdict", "") for d in M + R + U}
    wc = {d: (rows.get(norm(d)) or {}).get("wc") for d in M + R + U}
    m_ok = [d for d in M if v[d] not in NOT_ASSESSED]
    r_ok = [d for d in R if v[d] not in NOT_ASSESSED]
    g1 = len(m_ok) + len(r_ok) >= 36 and len(m_ok) >= 8
    g2 = version == WANT_VERSION and tests_exit == 0
    f1 = sum(1 for d in m_ok if v[d] == "disputed")
    f2 = sum(1 for d in r_ok if v[d] == "retracted")
    f3 = sum(1 for d in r_ok if v[d] == "disputed")
    f4 = sum(1 for d in m_ok if wc[d] is True)
    f5 = sum(1 for d in r_ok if wc[d] is True)
    m_retracted = sum(1 for d in m_ok if v[d] == "retracted")
    return {"G1_assessed": g1, "G2_version_and_tests": g2,
            "n_M_assessed": len(m_ok), "n_R_assessed": len(r_ok),
            "M_disputed": f1, "M_retracted": m_retracted, "R_retracted": f2, "R_disputed": f3,
            "M_flag_from_wc": f4, "R_flag_from_wc": f5,
            "F1": f1 >= 8, "F2": f2 >= 27, "F3": f3 <= 1, "F4": f4 >= 8, "F5": f5 <= 1,
            "verdicts": {d: v[d] for d in M + R + U}, "wc": {d: wc[d] for d in M + R + U}}


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-min", type=int, default=90)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    plan_live = script_live = None
    want = ('VERSION = "%s"' % WANT_VERSION).encode()
    deadline = time.monotonic() + 60 * a.wait_min
    while time.monotonic() < deadline and not (plan_live and script_live):
        if not plan_live:
            b = get(RAW + PLAN, tries=1)
            if b and PLAN_MARK in b:
                plan_live = now()
        if not script_live:
            b = get(RAW + SCRIPT, tries=1)
            if b and want in b:
                script_live = now()
        if not (plan_live and script_live):
            time.sleep(60)
    s = {"plan": PLAN, "plan_live_at": plan_live, "script_%s_live_at" % WANT_VERSION: script_live,
         "started": now()}
    if not plan_live:
        s["error"] = "plan not live; nothing run"
        _write(a.out_dir, s)
        return 0
    repo = tempfile.mkdtemp(prefix="rcc-")
    live = os.path.join(a.out_dir, "live")
    missing = []
    for f in FILES:
        b = get(RAW + f)
        if b is None:
            missing.append(f)
            continue
        for root in (repo, live):
            p = os.path.join(root, *f.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(b)
    s["missing_files"] = missing
    if SCRIPT in missing:
        s["error"] = "skill script not downloaded"
        _write(a.out_dir, s)
        return 2
    t = _run([sys.executable, "-m", "unittest", "test_retraction_crosscheck"], repo, 600)
    with open(os.path.join(a.out_dir, "repo_tests.txt"), "w", encoding="utf-8") as fh:
        fh.write(t.stdout + "\n" + t.stderr)
    s["repo_tests_exit"] = t.returncode
    vr = _run([sys.executable, os.path.join(repo, *SCRIPT.split("/")), "--version"], repo, 60)
    s["skill_version"] = (vr.stdout + vr.stderr).strip()
    dfile = os.path.join(repo, "dois.txt")
    with open(dfile, "w", encoding="utf-8") as fh:
        fh.write("\n".join(M + R + U) + "\n")
    t0 = time.monotonic()
    run = _run([sys.executable, os.path.join(repo, *SCRIPT.split("/")), "--file", dfile,
                "--json", "--max", "200"], repo, 3600)
    s["skill_exit"] = run.returncode
    s["skill_seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(a.out_dir, "skill_output.json"), "w", encoding="utf-8") as fh:
        fh.write(run.stdout)
    with open(os.path.join(a.out_dir, "skill_stderr.txt"), "w", encoding="utf-8") as fh:
        fh.write(run.stderr)
    rows = index_rows(run.stdout)
    if rows is None:
        s["error"] = "skill output not parsed"
        _write(a.out_dir, s)
        return 0
    g = grade(rows, s["skill_version"], s["repo_tests_exit"])
    s.update(g)
    s["all_gates_ok"] = g["G1_assessed"] and g["G2_version_and_tests"]
    out = [{"set": ("M" if d in M else "R_RNC" if d in R_RNC else "R_C" if d in R_C else "U"),
            "doi": d, "verdict": g["verdicts"][d],
            "pubmed_flag_from_withdrawn_correction": "" if g["wc"][d] is None else str(g["wc"][d]).lower()}
           for d in M + R + U]
    with open(os.path.join(a.out_dir, "verdicts.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["set", "doi", "verdict", "pubmed_flag_from_withdrawn_correction"])
        w.writeheader()
        w.writerows(out)
    _write(a.out_dir, s)
    shutil.rmtree(repo, ignore_errors=True)
    print(json.dumps({k: s.get(k) for k in ("skill_version", "G1_assessed", "G2_version_and_tests",
                                            "F1", "F2", "F3", "F4", "F5")}))
    return 0


class _Done:
    def __init__(self, returncode, stdout, stderr):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _run(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return _Done(p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return _Done(-9, out, "timeout after %ss" % timeout)


def _write(out_dir, s):
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
