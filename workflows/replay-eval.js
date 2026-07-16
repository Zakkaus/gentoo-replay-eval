export const meta = {
  name: 'ebuild-replay-eval',
  description: 'Ground-truth replay eval: clean-room agents reproduce real gentoo.git ebuild changes offline (with/without mined lessons), judged against held-out truth',
  phases: [
    { title: 'Solve', detail: '36 cases x 2 arms (with/without lessons), clean-room offline' },
    { title: 'Judge', detail: 'semantic compare each candidate vs held-out ground truth' },
  ],
}

const EVAL = '/home/zakk/code/gentoo-replay-eval'
const ids = Array.isArray(args) ? args : JSON.parse(args)

const SOLVE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['id', 'arm', 'wrote', 'note'],
  properties: {
    id: { type: 'string' }, arm: { type: 'string' },
    wrote: { type: 'boolean', description: 'candidate.ebuild was written' },
    note: { type: 'string', description: 'one line: what change you made, or what you could not derive offline' },
  },
}
const JUDGE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['id', 'arm', 'verdict', 'missing', 'extra', 'note'],
  properties: {
    id: { type: 'string' }, arm: { type: 'string' },
    verdict: { type: 'string', enum: ['correct', 'partial', 'wrong'] },
    missing: { type: 'integer', description: 'count of reference edits the candidate omitted' },
    extra: { type: 'integer', description: 'count of edits the candidate made that the reference did not (and that are wrong/unjustified)' },
    note: { type: 'string' },
  },
}

const tasks = ids.flatMap(id => [{ id, arm: 'with' }, { id, arm: 'without' }])

phase('Solve')
const results = await pipeline(
  tasks,
  (t) => agent(
`You are reproducing ONE real Gentoo ebuild change in a clean room, fully OFFLINE (no network, no fetching, no web). Ground truth exists but is hidden from you; producing the same result is the whole point.

Case id: ${t.id}   Arm: ${t.arm}
Repo root: ${EVAL}

Steps:
1. Read the task: ${EVAL}/cases/${t.id}/meta.json  (fields: pkg, ecosystem, task{kind,...}).
   - kind "bump": produce the ebuild for the NEW version (task.to_ver) from the OLD one (task.from_ver).
   - kind "fix": apply the change described in task.problem to the ebuild.
2. Read the current ebuild(s): ls ${EVAL}/cases/${t.id}/before/ and read them.
${t.arm === 'with'
  ? `3. Read the applicable mined maintenance lessons. Get the doc paths with:
     python3 ${EVAL}/lesson_map.py ${EVAL}/cases/${t.id}/meta.json
   Read the RELEVANT rules from those docs (grep for the ecosystem/eclass/idiom involved; do not dump whole files). Apply the conventions they encode (dep ordering, IUSE placement, eclass idioms, revbump/SRC_URI rules).`
  : `3. (No lessons provided in this arm.)`}
4. Write the corrected/updated ebuild file CONTENT to: ${EVAL}/runs/${t.id}/${t.arm}/candidate.ebuild
   (mkdir -p the dir first). Write the COMPLETE file, not a diff.

Hard rules:
- Do NOT read ${EVAL}/cases/${t.id}/truth/ — that is the held-out answer; reading it invalidates the eval.
- OFFLINE only. If a change genuinely needs upstream metadata you cannot have (new dependency versions, upstream flag renames, hackage/pypi revisions, distfile hashes), do NOT invent it — make the minimal defensible edit and append one final line \`# EVAL-NOTE: <what needed upstream data>\` (the scorer ignores trailing notes).
- Match Gentoo ebuild conventions exactly: keep the header, EAPI, ordering, quoting, and alphabetical dep/IUSE ordering consistent with the existing file.

Return the structured summary {id, arm, wrote, note}.`,
    { label: `solve:${t.arm}:${t.id}`, phase: 'Solve', schema: SOLVE_SCHEMA, effort: 'low' }
  ),
  (solved, t) => agent(
`Judge whether a candidate ebuild reproduced a real Gentoo change, by comparing it against the held-out reference (ground truth). Be adversarial: default to "partial" or "wrong" if the candidate omits any edit the reference made.

Case id: ${t.id}   Arm: ${t.arm}
- Intent:     ${EVAL}/cases/${t.id}/meta.json  (task.kind + version or problem)
- Before:     ${EVAL}/cases/${t.id}/before/    (state before the change)
- Reference:  ${EVAL}/cases/${t.id}/truth/     (the REAL committed result = ground truth)
- Candidate:  ${EVAL}/runs/${t.id}/${t.arm}/candidate.ebuild   (what the agent produced)

Read all four. Then diff candidate vs reference IN EFFECT, ignoring cosmetic-only differences (whitespace, copyright year, comment wording, trailing \`# EVAL-NOTE\` lines) and accepting alternative-but-equivalent phrasings. Focus on functional edits: version/SRC_URI, DEPEND/RDEPEND/BDEPEND, IUSE, REQUIRED_USE, eclass/EAPI, KEYWORDS, patches applied.

Verdict:
- correct = candidate achieves the SAME effective change as the reference (all functional edits present, none wrong).
- partial = some functional edits right, others missing or wrong.
- wrong   = missed the change entirely, or broke the ebuild, or the file is empty/unwritten.
missing = number of distinct reference edits the candidate omitted. extra = number of unjustified edits the candidate added that the reference did not.

If the candidate file does not exist or is empty, verdict=wrong, missing=high, note="no candidate".

Return {id, arm, verdict, missing, extra, note}.`,
    { label: `judge:${t.arm}:${t.id}`, phase: 'Judge', schema: JUDGE_SCHEMA, effort: 'low' }
  )
)

const ok = results.filter(Boolean)
// aggregate by (stratum-from-id, arm, verdict)
const strat = (id) => id.startsWith('fix') ? 'fix' : 'edit-bump'
const agg = {}
for (const r of ok) {
  const k = `${strat(r.id)}|${r.arm}`
  agg[k] = agg[k] || { n: 0, correct: 0, partial: 0, wrong: 0 }
  agg[k].n++; agg[k][r.verdict]++
}
log('JUDGE RESULTS by stratum|arm: ' + JSON.stringify(agg))
return { agg, verdicts: ok }
