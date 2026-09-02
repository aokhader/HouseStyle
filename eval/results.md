# Evaluation — A/B/C on held-out PRs

Generated 2026-09-02T04:09:09.482453+00:00.

Scored on **30 held-out apache/airflow PRs**, fenced off before sampling and never mined. Every one qualified at three or more review threads, so every one has real ground truth.

A finding matches a human comment when it is in the same file, within 5 lines, and the judge rules them semantically equivalent (MATCH or PARTIAL). Judge: `cache`, 41 cached verdicts reused.

| Condition | Recall | Ceiling | Precision | Findings/PR | Findings | Matched |
|---|---|---|---|---|---|---|
| A_baseline — stock review, no mined rules | 4.4% | 35.5% | 12.5% | 2.4 | 72 | 9 |
| B_housestyle — House Style, Airflow rules | 0.5% | 5.9% | 8.3% | 0.4 | 12 | 1 |
| C_generic — House Style, Home Assistant rules on Airflow PRs (unscoped) | 0.0% | 5.4% | 0.0% | 0.37 | 11 | 0 |

## What this evaluation found

**The mined rules did not outperform the baseline here.** Condition A — the same reviewer with no mined rules — anticipated more real human comments than condition B did, both strictly and leniently. The project's central claim, that mining a repository's review history produces better review than stock review of the same diffs, is **not supported by this run**. That is the result; it is not dressed up elsewhere in this report.

**A second tranche was run specifically to test whether the rulebook was simply too small. It was not the explanation.** Distilling tranche 2 grew the rulebook from 14 rules to 26 and the median applicable rules per PR from 7 to 14. Condition B was then re-run from scratch against the larger book. The result:

| | 14-rule book | 26-rule book |
|---|---|---|
| median applicable rules per PR | 7 | 14 |
| findings | 12 | 12 |
| strict matches | 0 | 0 |
| lenient matches | 1 | 1 |

Twice the rules, twice the rules in scope, and the same twelve findings and the same single lenient match. A different and broader set of rules fired (six distinct rules rather than four), so the rulebook did change — the *outcome* did not. That is evidence against 'the rulebook is too small' and for the harder reading: **rules mined from what reviewers did comment on do not predict what reviewers will comment on next.** Review is largely a specific maintainer noticing a specific thing, and much of it is not convention at all.

This does not make the rulebook worthless — the Phase 3 cross-check shows it contains real, evidenced, undocumented conventions, and reviewers in this run repeatedly noted diffs that *complied* with a rule. It means the rulebook is better understood as a documentation artifact and a checklist than as a predictor of the next review comment.

What the run does support: **condition C confirms the rules are repo-specific.** Another repository's rulebook, offered unscoped against these diffs, matched nothing. Whatever the Airflow rulebook is doing, it is not detecting generic Python smells.

## Reading these numbers

**Precision is measured against what a reviewer actually wrote, which is a subset of what they noticed.** A correct finding that no human bothered to comment on scores as a false positive here. The precision column is therefore a lower bound, and comparing precision *between* conditions is more meaningful than any single value.

**A_baseline isolates the lift as coming from the mining rather than the model.** Same reviewer, same diffs, no mined rules.

**Recall here is bounded by finding volume, not by rule quality.** Both reviewer prompts instruct the reviewer to prefer silence, because precision is what makes a review tool tolerable in practice. That decision caps recall arithmetically: a reviewer emitting well under one finding per PR cannot match a few hundred human comments however good those findings are. The ceiling is `findings / ground_truth`, and every condition here sits near it. Read recall as *of the few things it chose to say, how often was a human saying the same thing* — not as coverage of the review. A higher-verbosity run would trade this the other way, and the two settings measure different products.

The instruction is identical in both prompts, so the comparison between conditions is unaffected; only the absolute recall scale is.

**Thirty PRs do not exercise a whole rulebook.** Only a handful of mined rules fired at all here, and they were the ones the project already documents (CONFIRMED or IMPLIED in the cross-check). No TRIBAL rule fired — the undocumented conventions are the product, but they are also the rarer ones, and a 30-PR sample is too small to encounter most of them. That is a limit of the evaluation's size, not evidence about those rules. Scoring the rulebook properly would need a held-out set sized to the rules rather than to the calendar.

**C_generic is the ablation, and it is run deliberately unscoped.** Home Assistant rules applied to Airflow PRs. Both are large async Python infrastructure projects, so a C score near B would mean the rules are generic Python smells wearing a repository's name.

Run *with* the normal scope filter, condition C scores zero for an uninteresting reason: Home Assistant's scope paths (`homeassistant/components/...`, `tests/...`) cannot intersect Airflow's tree, so **all 27 rules are rejected before their content is ever examined** — 0 applicable rules on all 30 held-out PRs. That is a real result about path specificity, but it proves only that the *paths* differ. So C is scored with the scope filter disabled, offering every Home Assistant convention against every Airflow diff. That asks the question worth asking: do these conventions actually fire on another repository's code?

## B_housestyle — by category

| Category | Findings | Matched | Precision |
|---|---|---|---|
| commit-hygiene | 3 | 0 | 0.0% |
| docs | 3 | 0 | 0.0% |
| testing | 3 | 0 | 0.0% |
| api-design | 2 | 1 | 50.0% |
| correctness | 1 | 0 | 0.0% |

Rules that matched the most human comments:

- `airflow-r419` — 1 matched comments

## C_generic — by category

| Category | Findings | Matched | Precision |
|---|---|---|---|
| testing | 6 | 0 | 0.0% |
| api-design | 4 | 0 | 0.0% |
| correctness | 1 | 0 | 0.0% |
