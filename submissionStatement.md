# House Style — Submission Statement

## The problem

Every mature codebase has two rulebooks. One is written down: the linter config, the contributing guide, the hand-written `AGENTS.md`. The other lives in the heads of three or four senior reviewers and surfaces only when someone violates it in a pull request.

The second rulebook is where expensive review time goes. It is not formatting — CI catches that. It is *"cursor tokens that fail to parse must raise HTTP 400, not fall back to the raw string."* New contributors cannot know these conventions. Reviewers retype them for years. Nobody writes them down, because nobody holds the whole list; each reviewer carries a different fragment.

AI coding tools have made this worse. Every team now hand-writes an agent rules file full of guessed conventions, with no evidence behind any line and no way to tell which entries reflect what the team actually enforces.

## The solution

House Style mines a repository's merged-PR review history and distils the conventions reviewers genuinely enforce into an enforceable IBM Bob Skill.

**Target users** are maintainers and contributors on any codebase with review history — and, increasingly, the AI agents working in those codebases.

**Interaction** happens where developers already are. A maintainer runs the miner once; a contributor types `/house-style` in Bob IDE before opening a PR. Every finding cites the reviews behind it:

> `[airflow-r014]` Fetch limit+1 rows so `next_cursor` can be null on the last page.
> Precedent: PR #64845, #64963, #63994 (support: 3 reviews)

Rules stay editable markdown. Disagree with one? Delete it and commit.

## Why this is new

**Citations change the interaction.** Existing AI reviewers assert. House Style shows precedent, so a finding becomes arguable rather than oracular. That is the difference between a tool teams adopt and one they mute.

**We invert the agent rules file.** Apache Airflow ships a hand-written `AGENTS.md`. We cross-check it in both directions: which mined rules are already documented, and — more pointedly — **which of their hand-written rules review history does not support?** Hand-written agent rules are guesses. Ours are evidence with citations. Every judge maintains a rules file and has no idea which of their own entries are real.

**We prove specificity by ablation.** Our evaluation runs three conditions on 30 held-out PRs: stock Bob review, House Style with Airflow rules, and House Style with *Home Assistant* rules applied to Airflow PRs. Both are large async Python infrastructure projects — if the third scored well, we would only be detecting generic Python smells. IBM Granite on watsonx.ai judges semantic equivalence against real human comments.

## Why Bob specifically

Distillation is a map-reduce over 5,500 review comments — structurally impossible in one context window. Bob subagents extract candidates from 25-comment batches in parallel tranches; a chunked critic merges duplicates and thresholds on distinct-PR support. Bob's document understanding reads the `AGENTS.md`. The output ships as a Bob Skill, so adoption costs nothing.

We also measured when mining stops paying: rule discovery saturates, and we report the curve.

Conventions were always in the history. Nobody had read it.