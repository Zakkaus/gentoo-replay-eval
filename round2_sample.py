#!/usr/bin/env python3
# Round-2 sampler: reuse select_cases.build_case, but stratify to collect mostly
# NON-haskell edit-bumps (+ a few haskell as controls), so autobump_xcheck can test
# whether the `inherit haskell-cabal -> escalate` signal over-fires on other ecosystems.
#
#   GENTOO_CORPUS=/path/to/gentoo.git python3 round2_sample.py   # writes cases2/
#
# Needs a full gentoo.git checkout (blobless is fine): git clone --filter=blob:none
# --no-checkout https://github.com/gentoo/gentoo.git ../gentoo-corpus
# Ground truth for these cases is produced by a judge pass (workflows/) into
# cases2/verdicts.json ({id, reproducible}); then: CASES_DIR=cases2 RESULTS_DIR=cases2
# python3 autobump_xcheck.py
import sys, os, json, random
RE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RE)
os.environ.setdefault('GENTOO_CORPUS', os.path.join(os.path.dirname(RE), 'gentoo-corpus'))
import select_cases as sc

OUT = os.environ.get('CASES2_DIR', os.path.join(RE, 'cases2'))
WANT_NONHS = int(os.environ.get('WANT_NONHS', '25'))
WANT_HS = int(os.environ.get('WANT_HS', '6'))
SCAN_CAP = int(os.environ.get('SCAN_CAP', '6000'))
random.seed(int(os.environ.get('SEED', '1234')))

shas = [json.loads(l)['sha'] for l in open(sc.COMMITS) if json.loads(l).get('category') == 'bump']
random.shuffle(shas)

nonhs, hs, scanned = [], [], 0
for sha in shas:
    if len(nonhs) >= WANT_NONHS and len(hs) >= WANT_HS:
        break
    scanned += 1
    if scanned > SCAN_CAP:
        break
    try:
        c = sc.build_case(sha, 'edit-bump')
    except Exception:
        continue
    if not c:
        continue
    before = list(c['before'].values())[0]
    is_hs = 'haskell-cabal' in before
    if is_hs and len(hs) < WANT_HS:
        hs.append(c)
    elif (not is_hs) and len(nonhs) < WANT_NONHS:
        c['ecosystem'] = sc.ecosystem(before)
        nonhs.append(c)

cases = nonhs + hs
os.makedirs(OUT, exist_ok=True)
index = []
for i, c in enumerate(cases):
    before = list(c['before'].values())[0]
    c['is_haskell'] = 'haskell-cabal' in before
    c['id'] = f'r2-{i:03d}'
    d = os.path.join(OUT, c['id'])
    os.makedirs(os.path.join(d, 'before'), exist_ok=True)
    os.makedirs(os.path.join(d, 'truth'), exist_ok=True)
    for fn, t in c['before'].items(): open(os.path.join(d, 'before', fn), 'w').write(t)
    for fn, t in c['truth'].items(): open(os.path.join(d, 'truth', fn), 'w').write(t)
    meta = {k: c[k] for k in ('id', 'sha', 'stratum', 'pkg', 'ecosystem', 'task', 'is_haskell')}
    json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'), indent=1)
    index.append(meta)
json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)

from collections import Counter
print(f'scanned {scanned} bump commits; collected {len(cases)} edit-bumps '
      f'({len(nonhs)} non-haskell, {len(hs)} haskell)')
print('ecosystem spread (non-haskell):', dict(Counter(c['ecosystem'] for c in nonhs)))
print(f'written to {OUT}')
