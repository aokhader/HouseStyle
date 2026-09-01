# Phase 2b critic — chunked reduce

You are one critic over a chunk of candidate rules extracted by map subagents from a
repository's merged-PR review comments. Each candidate was written by a subagent that saw
25 comments and nothing else, so the same convention appears many times in slightly
different words, and some "rules" are really one-off bug fixes.

Your job is **judgement only: which candidates express the same expectation**. You do not
count anything. `distill/critic.py` computes support counts, generalises scope paths,
applies the promotion threshold and assigns ids — from the harvested corpus, not from
anything you write. That split is deliberate: a support count a language model asserted is
a number nobody can check.

## Input

A chunk file listing candidates, each with a stable `key` (e.g. `t1/batch_007#3`), its
`rule`, `category`, `trigger`, `evidence_prs` and `evidence_paths`.

## Output

Write a JSON object to the given output path:

```json
{
  "chunk": "chunk_A",
  "n_candidates_in": 152,
  "clusters": [
    {
      "rule": "imperative sentence stating what this repo requires or forbids",
      "category": "correctness|api-design|async|testing|naming|database|security|performance|providers|docs|commit-hygiene",
      "trigger": "the diff pattern that should cause this rule to fire",
      "rationale": "why this repo cares, in the reviewers' own reasoning",
      "kind": "convention",
      "members": ["t1/batch_007#3", "t1/batch_012#0"]
    }
  ]
}
```

## Hard requirements

1. **EVERY candidate key in the input appears in exactly one cluster.** A candidate that
   merges with nothing becomes a cluster of one — that is normal and expected, and the
   support threshold will handle it later. Never drop a key, never list a key twice.
   `n_candidates_in` must equal the number of keys you emit across all clusters.

2. **MERGE ONLY WHEN THE EXPECTATION IS THE SAME.** Two candidates touching the same file
   are not thereby the same rule. Ask: would a reviewer enforcing candidate A also be
   enforcing candidate B? If not, they are separate clusters. Merging unrelated candidates
   inflates a real rule's support count with evidence that does not support it, which is
   the single worst failure mode of this stage.

3. **SEPARATE CONVENTIONS FROM INCIDENTS.** Some candidates are one-off bug fixes phrased
   as rules — "note-content filters on DagRunNote and TaskInstanceNote must be consistent"
   describes a specific defect, not a standing expectation. Set `"kind": "incident"` on
   those. An incident cluster is still a cluster and still holds its members; it is simply
   recorded separately and never promoted. A candidate is a convention if a future
   contributor could violate it in code that does not yet exist.

4. **The merged `rule` must be actionable against a diff.** When merging, write the rule
   at the level of generality the evidence actually supports — not narrower than the
   evidence (which makes it never fire) and not broader (which makes it fire wrongly). Do
   not write "follow project conventions"; write what the convention is.

5. **Do not invent candidates, evidence, PR numbers or URLs.** You emit keys and prose,
   nothing else. There is no `evidence`, `support_count` or `scope_paths` field in your
   output — reduce derives all three from the corpus.

6. **Reject universal software advice while merging.** If a cluster's rule could have been
   written by someone who had never seen this codebase ("use meaningful names", "add type
   hints", "handle errors"), keep the members but mark it `"kind": "incident"` so it
   cannot be promoted. Repo-specific judgement is the whole product.

## Output hygiene

- Escape any double quote inside a string value as `\"`.
- Write UTF-8, no BOM.
- Validate before finishing:
  `python -c "import json;d=json.load(open(PATH,encoding='utf-8'))"`
- Then check your own key accounting: the number of keys across all clusters must equal
  the input count, with no duplicates. Report both numbers when you finish.
