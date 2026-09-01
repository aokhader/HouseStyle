# Phase 2b critic — MERGE

Three chunk critics each clustered a third of a tranche's candidates. None could see the
other two, so the same convention appears up to three times under different wording. Your
job is to find those and group them.

You see **cluster summaries only**, never raw candidates. The chunk critics already did
that reading, and `python -m distill.critic merge-expand` re-attaches the candidate keys
after you finish.

## Input

`distill/critic/t<N>/merge_input.json` — each cluster with a `cluster_id` (`A:12`, `B:3`,
`C:87`), its `rule`, `category`, `trigger`, `kind` and `n_candidates`.

## Output — only what merges

`distill/critic/t<N>/merged.json`:

```json
{
  "merges": [
    {
      "rule": "the merged rule, as one imperative sentence",
      "category": "correctness|api-design|async|testing|naming|database|security|performance|providers|docs|commit-hygiene",
      "trigger": "the diff pattern that should cause this rule to fire",
      "rationale": "why this repo cares, in the reviewers' own reasoning",
      "kind": "convention",
      "cluster_ids": ["A:12", "C:87"]
    }
  ],
  "demote": ["B:44"]
}
```

**List ONLY groups of two or more cluster_ids.** Every cluster you do not mention is kept
automatically as a rule of its own, with its original wording — that is handled in code,
so you never need to restate a cluster that merges with nothing. Most clusters will not
merge; that is expected and correct.

`demote` is optional: cluster_ids that should be reclassified as incidents because their
rule is universal software advice rather than a convention of this repository ("use
meaningful names", "add type hints", "extract a helper", "add tests"). Listing an id there
keeps it and its evidence, but bars it from promotion.

## Hard requirements

1. **No `cluster_id` appears in more than one merge group.** Verify with a script.

2. **MERGE ONLY WHEN THE EXPECTATION IS THE SAME.** This is where a bad merge does the
   most damage: merging pools the clusters' evidence, and the resulting support count is
   what the promotion threshold acts on. A rule that clears the bar on borrowed evidence
   is exactly the failure this pipeline exists to prevent.

   The test is not "same file", "same subsystem" or "both about testing". It is: **would a
   reviewer enforcing cluster A also be enforcing cluster B?** If a contributor could
   satisfy one and still violate the other, they are different rules — leave them apart.

3. **Never merge an incident into a convention.** If you group an incident cluster with
   anything, the whole group is treated as an incident. Incidents may merge with other
   incidents only when they are genuinely the same defect.

4. **Write the merged rule at the generality the evidence supports.** If merging forces
   you to write something vaguer than any of the inputs ("follow project conventions
   around X"), that is the signal they should not have merged.

5. Do not invent cluster ids, evidence, PR numbers or scope paths. There is no
   `scope_paths` or `support_count` field in your output — `distill/critic.py` derives
   both from the harvested corpus.

## Output hygiene

- Escape any double quote inside a string value as `\"`. Write UTF-8, no BOM.
- Validate: `python -c "import json;json.load(open(PATH,encoding='utf-8'))"`
- Check that no id repeats across groups, and that every id you used exists in the input.

Report: n_clusters_in, n_merge_groups, how many clusters those groups absorb, how many
ids you demoted, and the id-accounting result.
