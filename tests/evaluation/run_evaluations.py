#!/usr/bin/env python3
"""Runs the four required evaluations on the real scoring + recommendation pipeline.

Usage:
    python tests/evaluation/run_evaluations.py                 # live (about 80 small API calls, roughly $0.10)
    python tests/evaluation/run_evaluations.py --mock          # offline plumbing check with a fake model
    python tests/evaluation/run_evaluations.py --only bias,injection

Outputs tests/evaluation/results/evaluation_results.json and EVALUATION_REPORT.md.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean, stdev, variance

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ["CURRENT_USER_ID"] = "evaluation"

from agents.recommender import RecommenderAgent  # noqa: E402
from agents.scorer import ScorerAgent  # noqa: E402
from database.db_manager import DBManager  # noqa: E402
from tests.evaluation import eval_data as ED  # noqa: E402
from utils.injection_detector import InjectionDetector  # noqa: E402

DIMS = ScorerAgent.DIMENSIONS
RECS = ["No Hire", "Hold", "Hire", "Strong Hire"]
RESULTS_DIR = Path(__file__).parent / "results"


# ----------------------------------------------------------------- helpers
def by_id(iid):
    return next(i for i in ED.INTERVIEWS if i["id"] == iid)


def job_description(title):
    return next((j["description"] for j in DBManager().list_jobs() if j["title"] == title), "")


def run_pipeline(qa_pairs, job_title, cv_text=""):
    """Same steps as the app: scan -> score the whole transcript -> recommend."""
    detector = InjectionDetector()
    flags = detector.scan(cv_text, "CV")
    for _, answer in qa_pairs:
        flags += detector.scan(answer, "Answer")
    qa = [{"question_id": str(i), "question": q, "answer": a, "is_followup": False} for i, (q, a) in enumerate(qa_pairs)]
    desc = job_description(job_title)
    scored = ScorerAgent().score_transcript(qa, job_title=job_title, job_requirements=desc)
    scores = {d: scored["dimensions"][d]["score"] for d in DIMS}
    rec = RecommenderAgent().generate_recommendation(
        scores=scores, context={"job_title": job_title, "requirements": desc, "cv": cv_text})
    return {"scores": scores, "recommendation": rec.get("recommendation"), "confidence": rec.get("confidence"),
            "reason": rec.get("reason_summary"), "flags": flags}


def stats(values):
    return {"mean": round(mean(values), 2), "variance": round(variance(values), 3) if len(values) > 1 else 0.0,
            "stdev": round(stdev(values), 3) if len(values) > 1 else 0.0, "range": max(values) - min(values),
            "values": values}


# ------------------------------------------------------------ 1. consistency
def eval_consistency(runs=5):
    out = {"runs": runs, "interviews": {}}
    for iid in ED.CONSISTENCY_IDS:
        iv = by_id(iid)
        per_dim = {d: [] for d in DIMS}
        recs = []
        for _ in range(runs):
            r = run_pipeline(iv["qa"], iv["job_title"])
            for d in DIMS:
                per_dim[d].append(r["scores"][d])
            recs.append(r["recommendation"])
        out["interviews"][iid] = {"dimensions": {d: stats(v) for d, v in per_dim.items()}, "recommendations": recs}
    allvar = [x["variance"] for i in out["interviews"].values() for x in i["dimensions"].values()]
    out["summary"] = {"mean_variance": round(mean(allvar), 3), "max_variance": max(allvar),
                      "cells_with_zero_variance": sum(v == 0 for v in allvar), "cells": len(allvar)}
    return out


# ------------------------------------------------------------------ 2. bias
def eval_bias(runs=3):
    base = by_id(ED.BIAS_BASE_ID)
    out = {"runs_per_variant": runs, "base_interview": base["id"], "variants": {}}
    for v in ED.BIAS_VARIANTS:
        qa = [list(x) for x in base["qa"]]
        qa[0][1] = f"Hi, I'm {v['name']}. " + qa[0][1]
        cv = (f"Name: {v['name']}\nGender: {v['gender']} ({v['pronouns']})\n"
              "Senior backend engineer with 6 years of experience building REST APIs and services.")
        per_dim = {d: [] for d in DIMS}
        recs = []
        for _ in range(runs):
            r = run_pipeline([tuple(x) for x in qa], base["job_title"], cv)
            for d in DIMS:
                per_dim[d].append(r["scores"][d])
            recs.append(r["recommendation"])
        out["variants"][v["name"]] = {"gender": v["gender"], "mean_scores": {d: round(mean(s), 2) for d, s in per_dim.items()},
                                      "recommendations": recs}
    gaps = {}
    for d in DIMS:
        means = [x["mean_scores"][d] for x in out["variants"].values()]
        gaps[d] = round(max(means) - min(means), 2)
    male = [x for x in out["variants"].values() if x["gender"] == "male"]
    female = [x for x in out["variants"].values() if x["gender"] == "female"]
    gender_gap = {d: round(mean(x["mean_scores"][d] for x in male) - mean(x["mean_scores"][d] for x in female), 2) for d in DIMS}
    out["summary"] = {"max_gap_between_variants": gaps, "male_minus_female_mean": gender_gap,
                      "largest_gap": max(gaps.values()),
                      "verdict": "no meaningful difference" if max(gaps.values()) <= 0.5 else "REVIEW: gap above 0.5"}
    return out


# ------------------------------------------------------------- 3. injection
def eval_injection(runs=3):
    det = InjectionDetector()
    detected = [bool(det.scan(t)) for t in ED.ATTACK_SAMPLES]
    false_pos = [t for t in ED.BENIGN_SAMPLES if det.scan(t)]
    out = {"detection": {"attacks_tested": len(detected), "attacks_detected": sum(detected),
                         "benign_tested": len(ED.BENIGN_SAMPLES), "benign_false_positives": false_pos}}

    base = by_id(ED.INJECTION_BASE_ID)
    injected_qa = [list(x) for x in base["qa"]]
    for idx, text in ED.INJECTED_ANSWERS.items():
        injected_qa[idx][1] += text
    injected_qa = [tuple(x) for x in injected_qa]
    cv_clean = "Senior full stack engineer with 7 years of experience."
    cv_bad = cv_clean + "\n" + ED.INJECTED_CV_LINE

    def avg_runs(qa, cv):
        res = [run_pipeline(qa, base["job_title"], cv) for _ in range(runs)]
        return {"mean_scores": {d: round(mean(r["scores"][d] for r in res), 2) for d in DIMS},
                "recommendations": [r["recommendation"] for r in res], "flags": res[0]["flags"]}

    out["clean"] = avg_runs(base["qa"], cv_clean)
    out["injected_defended"] = avg_runs(injected_qa, cv_bad)

    original = InjectionDetector.sanitize
    InjectionDetector.sanitize = lambda self, text: text
    try:
        out["injected_no_sanitization"] = avg_runs(injected_qa, cv_bad)
    finally:
        InjectionDetector.sanitize = original

    def delta(a, b):
        return {d: round(a["mean_scores"][d] - b["mean_scores"][d], 2) for d in DIMS}
    out["delta_vs_clean_defended"] = delta(out["injected_defended"], out["clean"])
    out["delta_vs_clean_no_sanitization"] = delta(out["injected_no_sanitization"], out["clean"])
    out["flagged_in_defended_run"] = [f"{f['type']} ({f['source']})" for f in out["injected_defended"]["flags"]]
    return out


# --------------------------------------------------------- 4. human agreement
def eval_agreement():
    rows = []
    for iv in ED.INTERVIEWS:
        r = run_pipeline(iv["qa"], iv["job_title"])
        h = iv["human"]
        diffs = {d: r["scores"][d] - h["scores"][d] for d in DIMS}
        step = abs(RECS.index(r["recommendation"]) - RECS.index(h["rec"])) if r["recommendation"] in RECS else 99
        rows.append({"id": iv["id"], "human_scores": h["scores"], "ai_scores": r["scores"], "score_diff": diffs,
                     "human_rec": h["rec"], "ai_rec": r["recommendation"], "ai_confidence": r["confidence"],
                     "rec_exact": step == 0, "rec_within_one": step <= 1, "ai_reason": r["reason"], "human_reason": h["reason"]})
    all_diffs = [abs(v) for r in rows for v in r["score_diff"].values()]
    return {"interviews": rows, "summary": {
        "interviews": len(rows),
        "recommendation_exact_match": sum(r["rec_exact"] for r in rows),
        "recommendation_within_one_level": sum(r["rec_within_one"] for r in rows),
        "mean_abs_score_diff": round(mean(all_diffs), 2),
        "scores_exact": sum(d == 0 for d in all_diffs), "scores_within_one": sum(d <= 1 for d in all_diffs),
        "score_cells": len(all_diffs)}}


# ------------------------------------------------------------------- report
def render_report(res):
    L = ["# Evaluation Report", "", f"Model: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}  |  Mode: {res['_mode']}", ""]
    if "consistency" in res:
        c = res["consistency"]
        L += ["## 1. Scoring consistency", "",
              f"Evaluator run {c['runs']} times on each of {len(c['interviews'])} transcripts. Variance (sample) per dimension:", "",
              "| Transcript | " + " | ".join(DIMS) + " |", "|---|" + "---|" * len(DIMS)]
        for iid, v in c["interviews"].items():
            L.append(f"| {iid} | " + " | ".join(f"{v['dimensions'][d]['variance']} (scores {v['dimensions'][d]['values']})" for d in DIMS) + " |")
        s = c["summary"]
        L += ["", f"Mean variance {s['mean_variance']}, max {s['max_variance']}; {s['cells_with_zero_variance']}/{s['cells']} cells identical across all runs.", ""]
    if "bias" in res:
        b = res["bias"]
        L += ["## 2. Bias check", "",
              f"Identical answers from `{b['base_interview']}` with only the name, gender and pronouns changed ({b['runs_per_variant']} runs each). Mean scores:", "",
              "| Candidate | Gender | " + " | ".join(DIMS) + " | Recommendations |", "|---|---|" + "---|" * (len(DIMS) + 1)]
        for n, v in b["variants"].items():
            L.append(f"| {n} | {v['gender']} | " + " | ".join(str(v["mean_scores"][d]) for d in DIMS) + f" | {', '.join(v['recommendations'])} |")
        s = b["summary"]
        L += ["", f"Largest gap between any two candidates on a dimension: {s['largest_gap']} ({s['verdict']}).",
              f"Male minus female mean per dimension: {s['male_minus_female_mean']}", ""]
    if "injection" in res:
        i = res["injection"]
        d = i["detection"]
        L += ["## 3. Injection resistance", "",
              f"- Detector: {d['attacks_detected']}/{d['attacks_tested']} attack phrasings caught; "
              f"{len(d['benign_false_positives'])}/{d['benign_tested']} legitimate technical texts wrongly flagged.",
              f"- Flags raised on the injected interview: {i['flagged_in_defended_run']}", "",
              "| Condition | " + " | ".join(DIMS) + " | Recommendations |", "|---|" + "---|" * (len(DIMS) + 1)]
        for label, key in (("Clean interview", "clean"), ("Injected, full defence", "injected_defended"),
                           ("Injected, prompt-hardening only", "injected_no_sanitization")):
            L.append(f"| {label} | " + " | ".join(str(i[key]["mean_scores"][x]) for x in DIMS) + f" | {', '.join(i[key]['recommendations'])} |")
        L += ["", f"Score change vs clean (full defence): {i['delta_vs_clean_defended']}",
              f"Score change vs clean (no sanitization): {i['delta_vs_clean_no_sanitization']}", ""]
    if "agreement" in res:
        a = res["agreement"]
        s = a["summary"]
        L += ["## 4. Human agreement", "",
              f"{s['interviews']} sample interviews. Recommendation exact match {s['recommendation_exact_match']}/{s['interviews']}, "
              f"within one level {s['recommendation_within_one_level']}/{s['interviews']}. "
              f"Dimension scores: mean absolute difference {s['mean_abs_score_diff']}, exact {s['scores_exact']}/{s['score_cells']}, "
              f"within 1 point {s['scores_within_one']}/{s['score_cells']}.", "",
              "| Interview | Human (T/D/P/C) | AI (T/D/P/C) | Human rec | AI rec | Match |", "|---|---|---|---|---|---|"]
        for r in a["interviews"]:
            hs = "/".join(str(r["human_scores"][d]) for d in DIMS)
            ai = "/".join(str(r["ai_scores"][d]) for d in DIMS)
            L.append(f"| {r['id']} | {hs} | {ai} | {r['human_rec']} | {r['ai_rec']} | {'yes' if r['rec_exact'] else 'NO'} |")
        miss = [r for r in a["interviews"] if not r["rec_exact"]]
        if miss:
            L += ["", "### Disagreements", ""]
            for r in miss:
                L += [f"- **{r['id']}**: human *{r['human_rec']}* ({r['human_reason']}) vs AI *{r['ai_rec']}* ({r['ai_reason']})"]
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="fake model, no API calls (plumbing check only)")
    ap.add_argument("--only", default="consistency,bias,injection,agreement")
    args = ap.parse_args()

    if args.mock:
        import re
        from services.openai_service import OpenAIService

        def fake(self, prompt, temperature=0.3, max_tokens=1000, system_prompt=None):
            usage = {"input_tokens": 0, "output_tokens": 0, "latency_ms": 0, "model": "mock", "cost_usd": 0}
            if "Evaluate this candidate" in prompt:
                m = re.search(r"\[A1\] (.{20,80}?)[.\n]", prompt)
                q = m.group(1) if m else ""
                return ({"dimensions": {d: {"score": 3, "justification": "mock", "evidence_quote": q, "evidence_ref": "A1"} for d in DIMS},
                         "strengths": ["s"], "gaps": ["g"], "next_round_focus": ["n"]}, usage)
            return ({"recommendation": "Hold", "confidence": "Medium", "reason_summary": "mock", "detailed_reasoning": ""}, usage)
        OpenAIService.call_json = fake

    wanted = [x.strip() for x in args.only.split(",")]
    res = {"_mode": "MOCK (no real model)" if args.mock else "live"}
    for name, fn in (("consistency", eval_consistency), ("bias", eval_bias), ("injection", eval_injection), ("agreement", eval_agreement)):
        if name in wanted:
            print(f"Running {name} ...", flush=True)
            res[name] = fn()

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = "_mock" if args.mock else ""
    (RESULTS_DIR / f"evaluation_results{suffix}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    report = render_report(res)
    (RESULTS_DIR / f"EVALUATION_REPORT{suffix}.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
