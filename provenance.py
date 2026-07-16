#!/usr/bin/env python3
"""Record the eval-set provenance: which classified-commits source, seed, and strata.
Each case's sha is traceable to gentoo/gentoo, so the set is reproducible."""
import json, collections, os
idx = json.load(open("cases/index.json"))
c = collections.Counter(x["stratum"] for x in idx)
os.makedirs("results", exist_ok=True)
json.dump({"source_commits": os.environ.get("COMMITS", "../gentoo-tree-lessons/data/commits.jsonl"),
           "seed": int(os.environ.get("SEED", "7")), "n_cases": len(idx),
           "strata": dict(c.most_common()),
           "note": "each case sha is traceable to gentoo/gentoo; select_cases.py rebuilds from source"},
          open("results/PROVENANCE.json", "w"), indent=1)
print("provenance -> results/PROVENANCE.json")
