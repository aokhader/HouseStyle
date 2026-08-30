Repos used: apache/airflow (main) and home-assistant/core (contrast)
Reason is that when measuring the quality of the comments of the PRs we get this:

repo                         human subst medlen  PRs days est/mo  newest      verdict
------------------------------------------------------------------------------------------------
zulip/zulip                     99    52    128   22    4    390  2026-08-30  MARGINAL
home-assistant/core            100    74    255   28    1   2220  2026-08-30  EXCELLENT
autorope/donkeycar             100    38     80   16  807      1  2026-06-13  REJECT
scikit-learn/scikit-learn      100    60    144   18    5    360  2026-08-29  MARGINAL
pydantic/pydantic               57    25     96   44   27     28  2026-08-28  WEAK
prefecthq/prefect               29    26    298   21    4    195  2026-08-29  WEAK
apache/airflow                  99    68    223   37    1   2040  2026-08-30  EXCELLENT
supabase/supabase               24    12    121   38    2    180  2026-08-30  WEAK

Project plan: Review conventions mined from your own repo. Bob ingests the last few hundred merged PRs, extracts what human reviewers actually flag in that codebase, and emits a generated custom-rules file plus a /review Skill. Then you validate it by replaying held-out historical PRs and scoring precision/recall against the real human comments. A genuine eval on real data beats a demo video.

Project phases:
1. Phase 1 — Harvest (Python, no Bobcoins). Pull merged PRs from a target repo via the GitHub API. For each, capture line-anchored review comments plus the diff hunk they're attached to, and whether a commit afterward touched those lines (that flag separates real requests from chatter). Filter out bots, LGTM, emoji, and anything not anchored to code. Hash reviewer handles rather than storing them; the rules say no personal information, and you want that visible in your writeup. Log your source repos, since they also require a source list.
2. Phase 2 — Distill (Bob, Agent mode + subagents). This is where you earn the "orchestration, not autocomplete" points. Several hundred comment/diff pairs will not fit in one context window, so fan out subagents over batches, each extracting candidate rules in the form "reviewers in this repo require X, evidenced by PRs #A, #B." Then run a critic pass that merges duplicates, drops one-offs below an evidence threshold, and writes .bob/rules/ files plus a human-readable REVIEW_CONVENTIONS.md. Say this out loud in your demo: map-reduce over repo history is a thing a single prompt structurally cannot do.
3. Phase 3 — Ship it as a Skill. Build /house-style as a Bob Skill that loads the generated rules and reviews a diff. Every comment it emits cites the historical PRs that justify the rule. That citation is your design and creativity score in one feature, because unjustified AI review comments are the reason teams abandon these tools. Rules stay as editable markdown, so a reviewer who disagrees deletes a line and commits. Human-in-the-loop is the adoption story.
4. Phase 4 — Evaluate. Hold out the 30 most recent PRs, never touched during mining. Run three conditions on them: no review, stock Bob review with no mined rules, and House Style. Score recall (what fraction of real human comments did it anticipate) and precision. The stock-Bob baseline is the entire impact argument — it isolates the lift as coming from the mining, not from the model. Use a Granite model on watsonx.ai as the semantic judge for matching generated comments to real ones. That's a genuine reason to touch watsonx rather than a bolt-on.
5. Phase 5 — The demo. Run the pipeline against two different repos with visibly different cultures and show that the mined rules genuinely differ. That single side-by-side proves you're learning the repo rather than regurgitating a generic linter, and it's the moment that wins creativity. Wrap it in a small Next.js dashboard showing mined rules, their evidence PRs, and the eval scores. Your stack, and it's the difference between a 3 and a 5 on design.


Note: Three PRs hit the >50 review threads cap and were truncated. Those are your most-discussed PRs, so it's the wrong tail to lose, but raising reviewThreads(first:) to 100 doubles the point cost on all 1,500 fetches to rescue about 1%. Note it in the writeup as a documented sampling limitation instead.