# autobump decision-core cross-check

A second axis on top of the LLM-fix replay: does the deterministic engine
(`autobump-rb`) **escalate exactly the bumps that are not mechanically reproducible**?
For each edit-bump case we run `autobump-rb --check` on the before-state ebuild and
compare its mechanical/escalate decision to the held-out ground truth (can the real
ebuild be rebuilt offline, i.e. without the upstream metadata?).

Run: `make xcheck` (round-1) · `CASES_DIR=cases2 python3 autobump_xcheck.py` (round-2).

## Round-1 (18 edit-bumps, `cases/`, ground truth = held-out judge verdict)

| metric | before signal | after signal |
|---|---|---|
| escalation recall (caught metadata-driven) | **0/12 = 0%** | **11/12 = 92%** |
| escalation precision | – | 11/12 = 92% |
| reproducible cases not falsely escalated | 6/6 | 5/6 |

The blind spot: static classify (prerelease / major-jump / pins / patches) escalated
**0** of the 12 metadata-driven bumps. 11/12 were hackport/`haskell-cabal` — their dep
bounds, ghc/cabal floors and hackage revision are regenerated from the upstream `.cabal`,
so a version-only copy looks like a plain minor bump but keeps stale bounds. Fix: a new
classify signal, `inherit haskell-cabal -> escalate` (synced into `reference/autobump.sh`,
parity stays 10/10). Recall 0% → 92%. The one remaining FN is a prebuilt blob (dev-embedded),
caught by the stage-5 payload diff, not `--check`; the one FP is `dev-util/shellcheck`, which
*is* haskell-cabal — escalating it is conservatively correct.

## Round-2 (14 edit-bumps, `cases2/`, ecosystem-stratified, ground truth = judge pass)

Fresh sample (`round2_sample.py`, mostly non-haskell) to test whether the signal over-fires:

- **8 non-haskell cases: zero over-fire by the haskell signal.** The only non-haskell
  escalations are 2 rust (stalwart) bumps — caught by the pre-existing pins/CRATES signal
  (their `CRATES=` list is regenerated from the upstream `Cargo.lock`), not the haskell one.
- **6 haskell cases: all escalated.** Escalation **precision = 8/8 = 100%**.
- 6 FN are `app-emacs/*` revbumps. The judge calls them metadata-driven, but the diff is
  the *maintainer's packaging bundle* (EAPI 7→8, 9999 live-ebuild scaffolding, DOCS array) —
  not upstream data. A plain version bump is build-safe; the build gate + PR review cover the
  rest. So the FN here is a different class from haskell/rust "genuinely needs upstream data".

## Takeaway

Escalation is not only static major/prerelease/pins — **ecosystem shape (hackport-generated)
is itself a strong signal**, and only ground-truth replay exposed that the static core was
missing it. edit-bumps split two ways: *upstream-data-driven* (haskell `.cabal`, rust
`Cargo.lock`) — genuinely must escalate; and *maintainer packaging bundle* (EAPI/scaffolding)
— a mechanical bump is build-safe. The engine now escalates the first cleanly and precisely.
