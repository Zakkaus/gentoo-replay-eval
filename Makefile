CORPUS  ?= .corpus
COMMITS ?= ../gentoo-tree-lessons/data/commits.jsonl
.PHONY: cases score eval manifest check help
help: ## show targets
	@grep -E '^[a-z]+:.*##' Makefile | sed -E 's/:.*## / -- /'
cases: ## rebuild the eval set from the corpus + classified commits
	GENTOO_CORPUS=$(CORPUS) COMMITS=$(COMMITS) python3 select_cases.py
score: ## deterministic scoring of runs/ candidates vs held-out truth
	python3 score.py
manifest: ## record the eval-set provenance (source, seed, strata)
	python3 provenance.py
check: ## validate cases + scripts (what CI runs; no corpus needed)
	python3 check.py
eval: ## (re)run the clean-room solve+judge agents -- needs the Claude Code harness
	@echo "Run: Workflow({scriptPath: workflows/replay-eval.js, args: <case ids from cases/index.json>})"
