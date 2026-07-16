#!/usr/bin/env python3
"""Build a ground-truth replay eval set from gentoo.git history.

For each real commit we reconstruct the *before* state (parent) and hold out
the *after* state (the commit) as ground truth. A clean-room agent is later
asked to reproduce the change from before-state + a fair task statement + the
applicable mined lessons, WITHOUT seeing the answer. Output is scored by
normalized diff against ground truth. No compile needed -- matching the real
ebuild IS the proof (per the design brief).

Strata:
  rename-bump : new .ebuild is normalized-identical to old (mechanical path)
  edit-bump   : bump that also edits ebuild content (judgment path)
  fix         : in-place ebuild edit (code-gen path)

Fairness: the task never contains after-content. Manifests are excluded from
scoring (hashes need network). Copyright-year lines are normalized.
"""
import json, os, re, subprocess, random

REPO = "/var/tmp/gentoo-history"
COMMITS = "/var/tmp/gentoo-analysis/commits.jsonl"
OUT = "/home/zakk/code/gentoo-replay-eval/cases"
VER_RE = re.compile(r"^(?P<pn>.+?)-(?P<pv>\d[^/]*?)\.ebuild$")

def sh(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True).stdout

def show(ref, path):
    r = subprocess.run(["git", "-C", REPO, "show", f"{ref}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

def norm(txt):
    if txt is None: return None
    out = []
    for ln in txt.splitlines():
        if ln.startswith("# Copyright"): ln = "# Copyright"
        out.append(ln.rstrip())
    while out and not out[-1]: out.pop()
    return "\n".join(out)

def pn_pv(fn):
    m = VER_RE.match(os.path.basename(fn))
    return (m.group("pn"), m.group("pv")) if m else (None, None)

def files_of(sha):
    rows = []
    for ln in sh("show", "--name-status", "--format=", sha).splitlines():
        p = ln.split("\t")
        if len(p) >= 2: rows.append((p[0][0], p[-1]))
    return rows

def one_pkg(paths):
    pkgs = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 3 and "-" in parts[0]: pkgs.add(f"{parts[0]}/{parts[1]}")
    return next(iter(pkgs)) if len(pkgs) == 1 else None

def ecosystem(txt):
    if not txt: return "other"
    inh = " ".join(ln for ln in txt.splitlines() if ln.startswith("inherit ")).lower()
    if "distutils" in inh or "python" in inh: return "python"
    if "cargo" in inh or "go-module" in inh or "golang" in inh: return "rust-go"
    if "cmake" in inh or "meson" in inh or "autotools" in inh: return "c-cpp-build"
    if "perl-module" in inh: return "perl"
    if "java-pkg" in inh: return "java"
    if "linux-mod" in inh or "kernel" in inh: return "kernel"
    return "other"

def build_case(sha, want):
    rows = files_of(sha)
    pkg = one_pkg([p for _, p in rows])
    if not pkg: return None
    parent, eb = sha + "^", [(s, p) for s, p in rows if p.endswith(".ebuild")]
    if want in ("rename-bump", "edit-bump"):
        adds = [p for s, p in eb if s == "A"]; dels = [p for s, p in eb if s == "D"]
        if len(adds) != 1 or len(dels) != 1: return None
        newp, oldp = adds[0], dels[0]
        pn_new, pv_new = pn_pv(newp); pn_old, pv_old = pn_pv(oldp)
        if not pn_new or pn_new != pn_old or pv_new == pv_old: return None
        before, after = show(parent, oldp), show(sha, newp)
        if before is None or after is None: return None
        stratum = "rename-bump" if norm(before) == norm(after) else "edit-bump"
        if stratum != want: return None
        return dict(sha=sha, stratum=stratum, pkg=pkg, ecosystem=ecosystem(before),
                    task=dict(kind="bump", pkg=pkg, from_ver=pv_old, to_ver=pv_new,
                              old_file=os.path.basename(oldp), new_file=os.path.basename(newp)),
                    before={os.path.basename(oldp): before}, truth={os.path.basename(newp): after})
    if want == "fix":
        mods = [p for s, p in eb if s == "M"]
        if len(mods) != 1: return None
        p = mods[0]; before, after = show(parent, p), show(sha, p)
        if before is None or after is None or norm(before) == norm(after): return None
        subj = sh("show", "-s", "--format=%s", sha).strip()
        body = sh("show", "-s", "--format=%b", sha).strip()
        bug = re.search(r"[Bb]ug #?(\d{4,7})", subj + " " + body)
        return dict(sha=sha, stratum="fix", pkg=pkg, ecosystem=ecosystem(before),
                    task=dict(kind="fix", pkg=pkg, file=os.path.basename(p),
                              problem=subj, bug=(bug.group(1) if bug else None)),
                    before={os.path.basename(p): before}, truth={os.path.basename(p): after})
    return None

def main():
    random.seed(7)
    per = {"rename-bump": 12, "edit-bump": 18, "fix": 18}
    pools = {"bump": [], "fix": []}
    for l in open(COMMITS):
        o = json.loads(l)
        if o["category"] in pools: pools[o["category"]].append(o["sha"])
    for k in pools: random.shuffle(pools[k])
    cases, counts = [], {k: 0 for k in per}
    def drain(pool, wants):
        for sha in pool:
            if all(counts[w] >= per[w] for w in wants): break
            for w in wants:
                if counts[w] >= per[w]: continue
                c = build_case(sha, w)
                if c: cases.append(c); counts[w] += 1; break
    drain(pools["bump"], ["rename-bump", "edit-bump"])
    drain(pools["fix"], ["fix"])
    os.makedirs(OUT, exist_ok=True)
    for i, c in enumerate(cases):
        cid = f"{c['stratum']}-{i:03d}"; c["id"] = cid
        d = os.path.join(OUT, cid)
        os.makedirs(os.path.join(d, "before"), exist_ok=True)
        os.makedirs(os.path.join(d, "truth"), exist_ok=True)
        for fn, t in c["before"].items(): open(os.path.join(d,"before",fn),"w").write(t)
        for fn, t in c["truth"].items(): open(os.path.join(d,"truth",fn),"w").write(t)
        json.dump({k: c[k] for k in ("id","sha","stratum","pkg","ecosystem","task")},
                  open(os.path.join(d,"meta.json"),"w"), indent=1, ensure_ascii=False)
    print("selected:", counts, "total", len(cases))
    json.dump([{k:c[k] for k in ("id","sha","stratum","pkg","ecosystem","task")} for c in cases],
              open(os.path.join(OUT,"index.json"),"w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
