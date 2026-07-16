#!/usr/bin/env python3
"""Deterministic scorer: candidate ebuild vs held-out ground truth.

normalized-exact: norm(candidate) == norm(truth), where norm strips the
copyright-year line and trailing whitespace (neither is meaningful). This is
the strict "wrote the same thing" signal. Semantic correctness (multiple valid
ways to write the same edit) is judged separately by an agent in the workflow.
"""
import json, os, glob, sys

CASES = "cases"; RUNS = "runs"

def norm(txt):
    out = []
    for ln in txt.splitlines():
        if ln.startswith("# Copyright"): ln = "# Copyright"
        out.append(ln.rstrip())
    while out and not out[-1]: out.pop()
    return "\n".join(out)

def linescore(cand, truth):
    c, t = set(norm(cand).splitlines()), set(norm(truth).splitlines())
    inter = len(c & t)
    return dict(truth_lines=len(t), matched=inter,
                missing=len(t - c), extra=len(c - t),
                jaccard=round(inter / max(1, len(c | t)), 3))

def main():
    rows = []
    for meta_p in sorted(glob.glob(f"{CASES}/*/meta.json")):
        d = os.path.dirname(meta_p); cid = os.path.basename(d)
        meta = json.load(open(meta_p))
        truth_files = glob.glob(f"{d}/truth/*")
        if not truth_files: continue
        truth = open(truth_files[0]).read()
        for arm in ("with", "without"):
            cand_p = f"{RUNS}/{cid}/{arm}/candidate.ebuild"
            if not os.path.exists(cand_p): continue
            cand = open(cand_p).read()
            rows.append(dict(id=cid, stratum=meta["stratum"], ecosystem=meta["ecosystem"],
                             arm=arm, exact=(norm(cand) == norm(truth)), **linescore(cand, truth)))
    json.dump(rows, open("results/scores.json", "w"), indent=1)
    # aggregate
    import collections
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        k = (r["stratum"], r["arm"])
        agg[k]["n"] += 1
        agg[k]["exact"] += int(r["exact"])
        agg[k]["jac"] += r["jaccard"]
    print(f"{'stratum':12} {'arm':8} {'n':>3} {'exact%':>7} {'avg_jaccard':>12}")
    for (strat, arm), c in sorted(agg.items()):
        n = c["n"]
        print(f"{strat:12} {arm:8} {n:>3} {100*c['exact']/n:6.1f}% {c['jac']/n:11.3f}")
    return rows

if __name__ == "__main__":
    os.makedirs("results", exist_ok=True)
    main()
