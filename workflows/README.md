# workflows/

`replay-eval.js` is the **Claude Code Workflow script** that ran round-1: for each case it
spawns a clean-room solve agent per arm (with / without lessons, offline, no answer) then a
judge agent comparing the candidate against held-out ground truth. It carries the exact prompts.
It needs the Claude Code harness; the deterministic pieces (`select_cases.py`, `score.py`,
`lesson_map.py`) are standalone. Re-run: `Workflow({scriptPath: workflows/replay-eval.js, args: <case-ids>})`.
