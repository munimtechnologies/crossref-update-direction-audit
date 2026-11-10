#!/usr/bin/env python3
# Copyright 2026 MV2, Munim, Inc. (mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in MV2's name; no human has reviewed it.
"""EVAL-2: does the retraction-crosscheck skill call papers 'retracted' when PubMed's only
retraction notice for them is a withdrawn correction? See eval/EVAL-2-PLAN.md."""
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
PLAN = "eval/EVAL-2-PLAN.md"
FILES = ["skills/retraction-crosscheck/scripts/retraction_crosscheck.py",
         "skills/retraction-crosscheck/data/known_errors.csv",
         "skills/retraction-crosscheck/SKILL.md",
         "skills/retraction-crosscheck/CHANGELOG.md",
         "test_retraction_crosscheck.py"]
SCRIPT = FILES[0]
UA = "mv2-eval2/1.0 (mailto:mv2@munimtech.com)"

# M: PubMed "Retracted Publication" only via a withdrawn correction (GRADING-8, GRADING-9)
M = ["10.1016/j.cjca.2025.07.027", "10.1016/j.amjmed.2016.08.025", "10.1016/j.ejogrb.2015.07.009",
     "10.1016/j.intimp.2024.111636", "10.1016/j.wneu.2018.05.128", "10.1016/j.toxrep.2021.04.002",
     "10.1016/j.jaad.2022.12.023", "10.1016/j.jaad.2022.12.024", "10.1016/j.ijbiomac.2024.136739"]
# R: real retractions whose PubMed notice is titled as an erratum/correction (GRADING-9 hand check)
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


def index_results(text):
    """Map normalised DOI -> verdict from the skill's --json output. Accepts
    {"results": [...]} or a bare list; each row needs a DOI ('doi' or 'input') and a verdict
    ('verdict' or 'status'). Returns None if the text is not such JSON."""
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
        v = r.get("verdict") or r.get("status") or ""
        if doi:
            out[norm(str(doi))] = str(v)
    return out


def grade(verdicts):
    m = {d: verdicts.get(norm(d), "") for d in M}
    r = {d: verdicts.get(norm(d), "") for d in R}
    m_ok = [d for d in M if m[d] not in NOT_ASSESSED]
    r_ok = [d for d in R if r[d] not in NOT_ASSESSED]
    e1 = sum(1 for d in m_ok if m[d] == "retracted")
    e2 = sum(1 for d in r_ok if r[d] == "retracted")
    e3 = sum(1 for d in r_ok if r[d] == "disputed")
    g1 = len(m_ok) + len(r_ok) >= 36 and len(m_ok) >= 8
    return {"G1_assessed": g1, "n_M_assessed": len(m_ok), "n_R_assessed": len(r_ok),
            "M_retracted": e1, "R_retracted": e2, "R_disputed": e3,
            "E1": e1 >= 7, "E2": e2 >= 27, "E3": e3 <= 1,
            "M_verdicts": m, "R_verdicts": r,
            "U_verdicts": {d: verdicts.get(norm(d), "") for d in U}}


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-plan-min", type=int, default=40)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    plan_live = None
    deadline = time.monotonic() + 60 * a.wait_plan_min
    while time.monotonic() < deadline:
        b = get(RAW + PLAN, tries=1)
        if b and b"EVAL-2 plan" in b:
            plan_live = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            break
        time.sleep(60)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
    s = {"plan": PLAN, "plan_live_at": plan_live, "started": started, "missing_files": missing}
    if SCRIPT in missing:
        s["error"] = "skill script not downloaded"
        _write(a.out_dir, s)
        return 2
    t = _run([sys.executable, "-m", "unittest", "test_retraction_crosscheck"], repo, 600)
    with open(os.path.join(a.out_dir, "repo_tests.txt"), "w", encoding="utf-8") as fh:
        fh.write(t.stdout + "\n" + t.stderr)
    s["repo_tests_exit"] = t.returncode
    v = _run([sys.executable, os.path.join(repo, *SCRIPT.split("/")), "--version"], repo, 60)
    s["skill_version"] = (v.stdout + v.stderr).strip()
    dois = M + R + U
    dfile = os.path.join(repo, "dois.txt")
    with open(dfile, "w", encoding="utf-8") as fh:
        fh.write("\n".join(dois) + "\n")
    t0 = time.monotonic()
    run = _run([sys.executable, os.path.join(repo, *SCRIPT.split("/")), "--file", dfile,
                "--json", "--max", "200"], repo, 3600)
    s["skill_exit"] = run.returncode
    s["skill_seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(a.out_dir, "skill_output.json"), "w", encoding="utf-8") as fh:
        fh.write(run.stdout)
    with open(os.path.join(a.out_dir, "skill_stderr.txt"), "w", encoding="utf-8") as fh:
        fh.write(run.stderr)
    verdicts = index_results(run.stdout)
    if verdicts is None:
        s["error"] = "skill output not parsed"
        _write(a.out_dir, s)
        return 0
    g = grade(verdicts)
    s.update(g)
    s["all_gates_ok"] = g["G1_assessed"]
    rows = [{"set": "M", "doi": d, "verdict": g["M_verdicts"][d]} for d in M]
    rows += [{"set": "R_RNC" if d in R_RNC else "R_C", "doi": d, "verdict": g["R_verdicts"][d]}
             for d in R]
    rows += [{"set": "U", "doi": d, "verdict": g["U_verdicts"][d]} for d in U]
    with open(os.path.join(a.out_dir, "verdicts.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["set", "doi", "verdict"])
        w.writeheader()
        w.writerows(rows)
    _write(a.out_dir, s)
    shutil.rmtree(repo, ignore_errors=True)
    print(json.dumps({k: s.get(k) for k in ("skill_version", "G1_assessed", "E1", "E2", "E3")}))
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
