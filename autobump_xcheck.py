#!/usr/bin/env python3
# Cross-check the autobump-rb DECISION CORE against this repo's ground truth.
#
# For every edit-bump case, run `autobump-rb --check` on the before-state ebuild and
# compare its mechanical/escalate decision to whether the case is actually offline-
# reproducible (from the held-out verdicts). A metadata-driven bump (verdict "wrong":
# a clean-room agent could not reproduce it because the data lives in the upstream
# .cabal/metadata, not the ebuild) SHOULD be escalated, not bumped mechanically.
#
# This is a second axis on top of the LLM-fix replay: it asks "does the deterministic
# engine escalate exactly the bumps that are not mechanically reproducible?".
#
#   python3 autobump_xcheck.py
#   AUTOBUMP_BIN=/path/to/autobump-rb/bin/autobump python3 autobump_xcheck.py
#
# Env (zero absolute paths): CASES_DIR, RESULTS_DIR default beside this script;
# AUTOBUMP_BIN defaults to a sibling ../autobump-rb/bin/autobump.
import json, subprocess, tempfile, os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
CASES = os.environ.get('CASES_DIR', os.path.join(ROOT, 'cases'))
RESULTS = os.environ.get('RESULTS_DIR', os.path.join(ROOT, 'results'))
AB = os.environ.get('AUTOBUMP_BIN',
                    os.path.join(os.path.dirname(ROOT), 'autobump-rb', 'bin', 'autobump'))

idx = json.load(open(os.path.join(CASES, 'index.json')))

# Ground truth comes in two shapes: round-1 uses results/verdicts.json
# ({id, arm, verdict:correct/partial/wrong}); a re-sampled set (e.g. cases2) drops a
# CASES/verdicts.json ({id, reproducible: bool}) from a judge pass. Support both.
_cv = os.path.join(CASES, 'verdicts.json')
if os.path.exists(_cv):
    _v = json.load(open(_cv))
    GT = {x['id']: (x['reproducible'] is False) for x in _v}   # not reproducible -> should escalate
    LABEL = {x['id']: ('metadata' if x['reproducible'] is False else 'reproducible') for x in _v}
    JAC = {}
else:
    _v = [x for x in json.load(open(os.path.join(RESULTS, 'verdicts.json'))) if x['arm'] == 'without']
    GT = {x['id']: (x['verdict'] == 'wrong') for x in _v}
    LABEL = {x['id']: x['verdict'] for x in _v}
    JAC = {s['id']: s['jaccard'] for s in json.load(open(os.path.join(RESULTS, 'scores.json'))) if s['arm'] == 'without'}


def run_check(pkg, to, before):
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, pkg)
        os.makedirs(d)
        shutil.copy(before, d)
        env = dict(os.environ, AUTOBUMP_REPO=tmp)
        r = subprocess.run(['ruby', AB, pkg, to, '--check'],
                           capture_output=True, text=True, env=env, timeout=90)
        esc = [l[len('ESCALATE: '):] for l in r.stdout.splitlines() if l.startswith('ESCALATE:')]
        return r.returncode, esc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    rows = []
    for c in idx:
        if c['stratum'] != 'edit-bump':
            continue
        t = c['task']
        before = os.path.join(CASES, c['id'], 'before', t['old_file'])
        if not os.path.exists(before):
            continue
        ec, esc = run_check(t['pkg'], t['to_ver'], before)
        decision = {0: 'mechanical', 3: 'escalate', 2: 'abort'}.get(ec, f'exit{ec}')
        rows.append(dict(id=c['id'], pkg=t['pkg'], ver=f'{t["from_ver"]}->{t["to_ver"]}',
                         decision=decision, verdict=LABEL.get(c['id'], '?'), jac=JAC.get(c['id'], 0.0),
                         should_escalate=GT.get(c['id'], False), esc='; '.join(esc)[:50]))

    print(f'{"case":16} {"pkg":34} {"bump":22} {"autobump":11} {"verdict":8} {"jac":5}')
    for r in rows:
        flag = ''
        if r['should_escalate'] and r['decision'] != 'escalate':
            flag = '  <- MISSED'
        if (not r['should_escalate']) and r['decision'] == 'escalate':
            flag = '  <- over-escalate'
        print(f'{r["id"]:16} {r["pkg"]:34} {r["ver"]:22} {r["decision"]:11} '
              f'{r["verdict"]:8} {r["jac"]:.2f}{flag}')

    tp = sum(1 for r in rows if r['should_escalate'] and r['decision'] == 'escalate')
    fn = sum(1 for r in rows if r['should_escalate'] and r['decision'] != 'escalate')
    tn = sum(1 for r in rows if not r['should_escalate'] and r['decision'] != 'escalate')
    fp = sum(1 for r in rows if not r['should_escalate'] and r['decision'] == 'escalate')
    print(f'\n--- {len(rows)} edit-bump cases ---')
    print(f'ground-truth should-escalate (verdict wrong): {tp + fn} | reproducible: {tn + fp}')
    print(f'confusion vs ground-truth: TP={tp} FN={fn} TN={tn} FP={fp}')
    if tp + fn:
        print(f'escalation recall (caught metadata-driven): {tp}/{tp + fn} = {tp / (tp + fn):.0%}')
    if tp + fp:
        print(f'escalation precision: {tp}/{tp + fp} = {tp / (tp + fp):.0%}')
    print(f'reproducible cases not falsely escalated: {tn}/{tn + fp}')


if __name__ == '__main__':
    main()
