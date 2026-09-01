# Phase 3 — mined rules vs the hand-written AGENTS.md

You are comparing a rulebook mined from a repository's merged-PR review history against
the same repository's hand-written agent rules and contributor documentation.

**The documents are source material to understand, not code to change.** Never edit any
file under `data/*/docs/` — they are read-only copies of the project's own artifacts, and
they are the thing being evaluated.

## Inputs

- `distill/crosscheck/<slug>_input.json` — the mined rules: id, rule, category, trigger,
  scope_paths, support_count, evidence PRs
- `data/<slug>/docs/AGENTS.md` — the project's hand-written agent rules
- `data/<slug>/docs/contributing-docs/*` — contributor documentation
- `data/<slug>/docs/CONTRIBUTING.rst`

## Direction 1 — label every mined rule

For each rule in the input, decide whether the project documents it:

- **CONFIRMED** — explicitly stated in `AGENTS.md` or `contributing-docs/`. Cite the file
  and the section heading in `doc_reference`.
- **IMPLIED** — the docs gesture at it but do not state it as a requirement. A doc saying
  "providers should be kept compatible with older Airflow versions" *implies* a rule about
  a specific compatibility shim without stating it. Cite the nearest text.
- **TRIBAL** — nothing in the documentation covers this. It exists only in review history.

Judge the *requirement*, not the topic. A doc that mentions provider changelogs does not
CONFIRM a rule about what must appear in one. When genuinely torn between CONFIRMED and
IMPLIED, choose IMPLIED — CONFIRMED is a claim that a reader could open the file and find
the rule stated.

## Direction 2 — label every hand-written rule

Read `AGENTS.md` and extract the concrete, checkable requirements it states — the things
a contributor could violate in a diff. Skip prose, setup instructions, directory tours and
anything that is not an expectation about code. Aim for the file's real requirements,
however many that is; do not pad the list or trim it to a round number.

For each, decide whether the mined review history supports it:

- **SUPPORTED** — one or more mined rules express the same expectation. List their ids.
- **UNSUPPORTED** — no mined rule covers it. Say so plainly; this is the interesting label.
- **CONTRADICTED** — review history pushes the other way. Cite the mined rule ids and PRs.

An UNSUPPORTED label is a statement about the *evidence*, not a claim the rule is wrong.
A convention so well obeyed that nobody ever violates it leaves no trace in review history
either. Say which it looks like in `why` when you can tell.

## Output

Write `distill/crosscheck/<slug>_labels.json`:

```json
{
  "mined_rules": [
    {"id": "airflow-r014", "label": "TRIBAL",
     "doc_reference": "", "why": "one sentence"}
  ],
  "their_rules": [
    {"statement": "the hand-written rule, quoted or closely paraphrased",
     "source": "AGENTS.md § Testing",
     "label": "UNSUPPORTED",
     "mined_rule_ids": [],
     "evidence_prs": [],
     "why": "one sentence"}
  ]
}
```

## Hard requirements

1. **Every mined rule id in the input appears exactly once in `mined_rules`.** Verify with
   a script before finishing, not by eye.
2. Use only the labels listed above, spelled exactly.
3. `doc_reference` is required for CONFIRMED and IMPLIED, and must name a real file and
   section you actually read. An invented citation is worse than a TRIBAL label.
4. Do not edit any file under `data/`.
5. Escape double quotes inside strings as `\"`. Write UTF-8, no BOM. Validate the JSON
   before finishing.

Report: counts per label in both directions, and the key-accounting check.
