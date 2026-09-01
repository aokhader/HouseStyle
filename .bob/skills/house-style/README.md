# /house-style

A review Skill whose rules came from your repository's own merged pull requests, and
whose every finding cites the reviews it learned from.

```
/house-style                          review the working tree against main
/house-style --diff release-3.1       review against another base
/house-style --rules .bob/rules/hass-conventions.json
/house-style --explain airflow-r014   one rule, all its evidence
```

## What is in here

| Path | What it is |
|---|---|
| `SKILL.md` | the Skill itself — the procedure the agent follows |
| `scripts/house_style.py` | the deterministic parts: scope filter, renderer, `--explain` |
| `../../rules/airflow-conventions.md` | the rulebook, human-readable |
| `../../rules/airflow-conventions.json` | the rulebook, machine-readable |
| `../../rules/airflow-candidates.md` | patterns below the support threshold, and incidents |

## The division of labour

The agent decides whether a rule is violated. The script does everything around that,
because those are the steps where an agent quietly goes wrong:

- **Scope filtering.** Only rules whose `scope_paths` intersect the changed files are
  loaded. A two-file diff should not drag 200 rules into context — rules that cannot
  apply are where false positives come from.
- **Precedent enforcement.** `render` drops any finding whose rule has no resolvable
  evidence. This is the design's load-bearing constraint, so it is code and not a request
  in prose.
- **Support ordering.** Findings sort by how many distinct PRs back the rule, so the
  conventions your team enforces most often are read first.

## The intended workflow: edit the rulebook

**The rulebook is a text file under version control, and disagreeing with it is a normal
part of using this.**

A rule your team does not actually hold — mined from three reviews that happened to
agree, or a convention you have since abandoned — should be removable in one line:

```bash
# delete the rule's section from the markdown
$EDITOR .bob/rules/airflow-conventions.md
git commit -m "house-style: drop airflow-r041, we no longer require this"
```

The deletion shows up in review like any other change, so removing a rule is a decision
the team makes together rather than a setting one person flips. That is the point:
mined conventions are a **proposal**, and the committed rulebook is the record of what
your team decided to keep.

Other ways to disagree, in increasing order of bluntness:

- **Raise the bar.** Every rule carries `support_count`, the number of distinct PRs
  behind it. If support-3 rules feel like noise, filter the JSON to `support_count >= 5`
  and see what survives.
- **Narrow the scope.** A rule firing too widely usually has a `scope_paths` that
  generalised one level too far. Edit the path; it is just a prefix.
- **Reword it.** The `rule` text is what the agent evaluates and what the finding
  restates. If it is ambiguous, say it better — the evidence stays attached.

Re-running the distillation proposes deleted rules again from the same evidence, because
the evidence has not changed. That is a feature: the mining is reproducible and does not
remember your edits. Keep the rulebook in git and let the diff show what you changed.

## Checking a rule before trusting it

```bash
python .bob/skills/house-style/scripts/house_style.py explain airflow-r014
```

prints the rule, its full evidence with permalinks, and its `AGENTS.md` cross-check
label:

- **CONFIRMED** — the project documents this. The mining agrees with the docs.
- **IMPLIED** — the docs gesture at it without stating it as a requirement.
- **TRIBAL** — documented nowhere. It exists only in review history. This group is the
  reason the project exists.

Open two or three of the evidence links before you adopt a rule. If the comments do not
say what the rule says, the rule is wrong and deleting it is the right move.

## Limits worth knowing

- **Conventions nobody violates are invisible.** Rules come from what reviewers
  *commented on*. A convention so well understood that it never comes up leaves no trace
  in review history. This complements a hand-written `AGENTS.md`; it does not replace one.
- **Recency.** Rules reflect the window that was harvested. A convention the team dropped
  eight months ago can still have three supporting comments.
- **Scope is a prefix, not a semantic boundary.** A rule scoped to `providers/` fires on
  every provider, including ones whose maintainers never agreed to it.
