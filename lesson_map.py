#!/usr/bin/env python3
import json, sys, os
LDIR = os.environ.get("LESSONS_DIR") or next((p for p in [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gentoo-tree-lessons", "docs"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")] if os.path.isdir(p)), "docs")
ECO = {"python":"python.md","rust-go":"rust-go.md","c-cpp-build":"c-cpp-build.md",
       "perl":"perl.md","java":"java.md","kernel":"kernel.md","other":"general-hygiene.md"}
def docs_for(meta):
    out = [ECO.get(meta["ecosystem"], "general-hygiene.md")]
    if meta["task"]["kind"] == "fix":
        out += ["qa-fixes.md", "deps-revbump.md", "eclass-migrations.md"]
    else:
        out += ["src-upstream.md", "deps-revbump.md"]
    seen, res = set(), []
    for d in out:
        p = os.path.join(LDIR, d)
        if d not in seen and os.path.exists(p): res.append(p); seen.add(d)
    return res
if __name__ == "__main__":
    print("\n".join(docs_for(json.load(open(sys.argv[1])))))
