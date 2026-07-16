# gentoo-replay-eval

用真实提交做真值,验证「挖出来的经验 + 确定性脚本」到底能不能复现真实的 ebuild 工作。
Ground-truth replay eval: does the mined experience + deterministic scripts actually
reproduce real Gentoo ebuild work? Roll the tree back to *before* a real commit, have a
clean-room agent redo it offline, then diff against the real commit. Matching the real
ebuild *is* the proof — no compile needed.

## 背景 / Why

我们从 gentoo 主仓库挖了 706 条带出处的经验规则(见 `Zakkaus/gentoo-tree-lessons`),
又在 overlay 的 `autobump` 分支上有一套纯机械的 bump 脚本(`autobump.sh`,遇到非机械变更
就 `exit 3` 交给 LLM/人判断)。缺的是**真值验证**:这些经验和脚本是不是真的能干活、能泛化。
git 历史就是现成的真值。

We mined 706 sourced lessons from the gentoo tree (`Zakkaus/gentoo-tree-lessons`) and have a
purely mechanical bump engine on the overlay's `autobump` branch (`autobump.sh`, which stops at
`exit 3` and hands the evidence to an LLM/human when a change is not mechanical). What was missing
is **ground-truth validation** that the experience and scripts generalize. Git history is the
ground truth.

## 架构 / Architecture

分工(团队讨论后的结论):
- **脚本 = 确定性操作工具箱**(`autobump.sh` 等)。bump 在不 breaking 的情况下是确定的,
  脚本做机械操作;不确定就 `exit 3` 出证据包。
- **LLM = 判断 / 代码生成**。ebuild 本质是 shell 脚本,fix 就是代码生成 —— 不去硬写脚本特化,
  让 LLM 改,**我们做 QA**。经验库喂给 LLM 当上下文。
- **QA 层 = 本仓库**。用 git 历史做真值回放,量化 LLM+经验的复现能力。
- **泛化闸**:把反复出现的 fix 提炼成脚本操作时,review 必须确认它是通用的,不是针对某个包特化的。
- **节奏**:优先扫新增的包,再回填老的。

Division of labor (the team's conclusion):
- **Script = deterministic op toolbox** (`autobump.sh` et al). A non-breaking bump is deterministic;
  the script does the mechanical work and emits an evidence pack at `exit 3` when it is not.
- **LLM = judgment / code-gen.** An ebuild is a shell script, so a fix is code generation — do not
  hard-code package-specific script special-cases; let the LLM write the fix and **we build the QA**.
  The lessons feed the LLM as context.
- **QA layer = this repo.** Replay git history as ground truth and quantify how well LLM+lessons reproduce it.
- **Generality gate:** when a recurring fix is promoted into a script op, review must confirm it is
  general, not specialized to one package.
- **Cadence:** scan new packages first, then backfill old ones.

## 评测方法 / How the replay eval works

对每个真实提交 C(改了包 P):
1. `select_cases.py` 取 P 在 parent(C) 的状态作为 **before**(干净、离线的环境),把 C 的结果作为
   **truth** 藏起来。
2. clean-room agent 只拿到 before ebuild + 任务意图(bump 的目标版本 / fix 的问题描述)+ 对应生态的
   经验文档,**不联网、不给答案**,产出它认为正确的 ebuild。
3. `score.py` 做确定性归一化比对(忽略版权年份和纯空白),judge agent 做语义比对(允许等价写法)。
4. **消融**:每个用例跑两遍 —— 给经验 vs 不给经验 —— 直接量化经验的贡献。

For each real commit C touching package P:
1. `select_cases.py` takes P at parent(C) as the **before** state (a clean, offline environment) and
   holds out C's result as **truth**.
2. A clean-room agent gets only the before ebuild + the change intent (bump target version / fix problem
   statement) + the ecosystem's lesson doc — **offline, no answer** — and produces the ebuild it believes
   is correct.
3. `score.py` does a deterministic normalized compare (ignoring copyright year and pure whitespace); a judge
   agent does a semantic compare (equivalent phrasings allowed).
4. **Ablation:** every case runs twice — with lessons vs without — to quantify the lessons' contribution directly.

## 数据分层与公平性 / Strata & fairness

- `edit-bump` —— 换版本且改了 ebuild 内容(新依赖、SRC_URI、eclass 版本…)。注意:有些 bump 的正确
  结果需要**上游元数据**(新的 cabal / pyproject / Cargo.toml、hackage revision、flag 改名),离线拿不到 ——
  这类用例 agent 复现不了是**真实信号**,正好对应 `autobump.sh` 会 `exit 3` 升级的地方。
- `fix` —— 就地改 ebuild 修问题。任务意图来自真实 commit 标题,所以这测的是「**给定要做什么,能不能产出
  风格正确、字节正确的 ebuild**」,不是从零诊断。这正是「LLM 改、我们做 QA」的分工。
- Manifest 不计分(哈希要联网);版权年份、纯空白归一化。

- `edit-bump` — version change that also edits ebuild content (new deps, SRC_URI, eclass version, ...). Note:
  some bumps require **upstream metadata** (a new cabal/pyproject/Cargo.toml, a hackage revision, a flag rename)
  that is not in the before-state; a clean-room agent legitimately *cannot* reproduce those offline — a true
  signal that maps exactly onto where `autobump.sh` escalates at `exit 3`.
- `fix` — in-place ebuild edit. The intent comes from the real commit subject, so this measures "**given what
  to do, can it produce a style-correct, byte-correct ebuild**", not from-scratch diagnosis — the "LLM writes,
  we QA" division.
- Manifests are not scored (hashes need network); copyright year and pure whitespace are normalized.

## 结果 / Results

见 `results/SUMMARY.md`。一句话:**fix 这条「AI 改、我们 QA」的路走得通**(44% 判定正确、89% 正确或部分,0.94 行 jaccard);
**edit-bump 这批多是 Haskell/hackport 靠上游 .cabal 重生成的,离线复现不了(~0%),经验也补不了缺的数据** ——
这正好是 autobump.sh 该 `exit 3` 升级的地方。经验消融在 fix 上有小幅提升。完整表格和注意事项见 `results/SUMMARY.md`。

See `results/SUMMARY.md`. In one line: **the "AI writes the fix, we QA it" path works** (44% judge-correct, 89%
correct-or-partial, 0.94 line-jaccard); **edit-bumps in this sample are mostly Haskell/hackport regenerated from the
upstream .cabal, so offline reproduction is ~0% and lessons cannot supply the missing data** -- exactly where
autobump.sh escalates at `exit 3`. Lessons give a small lift on fixes. Full table and caveats in `results/SUMMARY.md`.

## 如何扩展 / Extending

- 加用例:`python3 select_cases.py`(采样在 `select_cases.py` 顶部的 `per`)。用例是 gentoo/gentoo 的
  真实快照,直接 commit 进 `cases/` 当 fixture。
- 加操作:确定性 bump 操作住在 overlay 的 `autobump` 分支;这里只做验证。把反复出现的 fix 提炼成操作前,
  先过泛化 review。
- 常态化:优先跑新增包(scan 模式),再回填老提交(backfill)。把调好的提示词存档。

- Add cases: `python3 select_cases.py` (sampling in `per` at the top). Cases are real gentoo/gentoo snapshots,
  committed under `cases/` as fixtures.
- Add ops: deterministic bump ops live on the overlay's `autobump` branch; this repo only validates. Run a
  generality review before promoting a recurring fix into an op.
- Normalize: scan new packages first, backfill old commits later; archive the tuned prompts.

## 脚本与数据 / Scripts & data

- `select_cases.py` / `score.py` / `lesson_map.py` — 确定性,可独立运行 / deterministic, standalone.
- `workflows/replay-eval.js` — 跑 round-1 的 Claude Code 工作流脚本(clean-room solve + judge,含原始提示词)/
  the Claude Code workflow that ran round-1 (clean-room solve + judge, exact prompts).
- `cases/` — gentoo/gentoo 真实快照做的 fixture / real gentoo/gentoo snapshots as fixtures.
  语料分类来自 `gentoo-tree-lessons` 的 `data/commits.jsonl` / case selection draws on that repo's classified corpus.

## 说明 / Notes

- 语言:harness 用 Python(与 pkgcheck/pkgdev/nvchecker 生态一致,也复用已有的 commit 分类器)。确定性
  操作是 language-thin 的 CLI,用 Ruby 写 shell 胶水层同样可以 —— 操作本身就是 shell 包装,语言不是承重的。
- 用例内容引自 gentoo/gentoo(GPL-2),本仓库 GPL-2。
- The harness is Python (aligns with the pkgcheck/pkgdev/nvchecker ecosystem and reuses the existing commit
  classifier). Deterministic ops are a language-thin CLI; a Ruby shell-glue layer works equally well since ops
  are shell wrappers — the language is not load-bearing. Case content is quoted from gentoo/gentoo (GPL-2); this repo is GPL-2.
