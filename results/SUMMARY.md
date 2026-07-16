# Round-1 results (36 real gentoo.git commits, 2026-07)

144 clean-room agents: each of 36 cases solved twice (with / without the mined
lessons), each candidate judged against held-out ground truth. Deterministic
normalized-exact + jaccard from `score.py`; correct/partial/wrong from the judge.

**Run:** 144 agents total — 72 clean-room solve (36 cases × 2 arms) + 72 judge — all completed,
0 errors. Model: **Claude Opus 4.8** (`claude-opus-4-8`, 1M context; the session model at run
time), ~2.7M subagent output tokens, run within a Claude subscription (no extra cost). The mining
that produced the lessons (`gentoo-tree-lessons`) was a separate round on Claude Fable 5.

| stratum   | arm     | n  | exact% | jaccard | judge correct | +partial |
|-----------|---------|----|--------|---------|---------------|----------|
| fix       | with    | 18 | 33.3%  | 0.938   | 8 (44%)       | 16 (89%) |
| fix       | without | 18 | 33.3%  | 0.936   | 7 (39%)       | 16 (89%) |
| edit-bump | with    | 18 | 0.0%   | 0.407   | 1 (6%)        | 6 (33%)  |
| edit-bump | without | 18 | 0.0%   | 0.377   | 1 (6%)        | 6 (33%)  |

## What it says

- **Fixes work, and are QA-able.** Given the change intent + lessons, a clean-room
  agent reproduces the real ebuild edit correctly ~44% of the time and correct-or-partial
  ~89%; where not byte-exact it is very close (0.94 line-jaccard on small localized edits).
  This is the "LLM writes the fix, we QA it" path -- it holds up. Lessons give a small
  lift (+1 correct, judge).
- **Edit-bumps in this sample are metadata-driven and not offline-reproducible.** 12/18
  are Haskell/hackport revbumps whose correct result is regenerated from the upstream
  `.cabal` (dep bounds, ghc version, `gmp`->`simd` flag rename, `CABAL_HACKAGE_REVISION`).
  A clean-room offline agent cannot invent that data, so exact% is 0 and the lessons
  ablation is flat (the bottleneck is missing DATA, not missing experience). This is a
  TRUE signal: these are exactly the bumps `autobump.sh` hands to the fetch/judge path at
  `exit 3`, not something to solve from the ebuild alone.

## Caveats / next round

- The edit-bump sampler oversampled Haskell (they drop+add a single ebuild, which the
  selector keys on). Stratify by ecosystem next round, and split edit-bumps into
  offline-reproducible (EAPI bumps, git-r3 scaffolding -- some scored correct here) vs
  metadata-dependent.
- Fix task intents come from the real commit subject (states what to do), so this measures
  faithful style-correct application, not from-scratch diagnosis. A symptom-only variant is
  the harder follow-up.
- Manifests excluded (need network); copyright year + whitespace normalized.
