'use client';

import { useMemo, useState } from 'react';
import type { CrossCheckLabel, Rule } from '@/lib/data';

const LABELS: CrossCheckLabel[] = ['TRIBAL', 'IMPLIED', 'CONFIRMED'];

export function RuleBrowser({
  rules,
  labels,
  categories,
}: {
  rules: Rule[];
  labels: Record<string, CrossCheckLabel>;
  categories: string[];
}) {
  const [cat, setCat] = useState<string | null>(null);
  const [label, setLabel] = useState<CrossCheckLabel | null>(null);

  const catCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of rules) m[r.category] = (m[r.category] ?? 0) + 1;
    return m;
  }, [rules]);

  const labelCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of rules) {
      const l = labels[r.id];
      if (l) m[l] = (m[l] ?? 0) + 1;
    }
    return m;
  }, [rules, labels]);

  const shown = rules.filter(
    (r) => (!cat || r.category === cat) && (!label || labels[r.id] === label),
  );

  const hasLabels = Object.keys(labels).length > 0;

  return (
    <>
      <div className="filters">
        <div className="group">
          <span className="label">Category</span>
          <button
            className="chip"
            aria-pressed={cat === null}
            onClick={() => setCat(null)}
          >
            all<span className="count">{rules.length}</span>
          </button>
          {categories.map((c) => (
            <button
              key={c}
              className="chip"
              aria-pressed={cat === c}
              onClick={() => setCat(cat === c ? null : c)}
            >
              {c}
              <span className="count">{catCounts[c] ?? 0}</span>
            </button>
          ))}
        </div>
        {hasLabels && (
          <>
            <span className="divider" />
            <div className="group">
              <span className="label">vs AGENTS.md</span>
              {LABELS.map((l) => (
                <button
                  key={l}
                  className="chip"
                  aria-pressed={label === l}
                  onClick={() => setLabel(label === l ? null : l)}
                >
                  {l.toLowerCase()}
                  <span className="count">{labelCounts[l] ?? 0}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <p className="note" style={{ marginBottom: 18 }}>
        Showing <b>{shown.length}</b> of {rules.length} rules.
      </p>

      <div className="cards">
        {shown.map((r) => (
          <RuleCard key={r.id} rule={r} label={labels[r.id]} />
        ))}
      </div>
    </>
  );
}

function RuleCard({ rule, label }: { rule: Rule; label?: CrossCheckLabel }) {
  const prs = Array.from(new Set(rule.evidence.map((e) => e.pr))).sort((a, b) => b - a);
  return (
    <article className="card">
      <div className="card-head">
        <span className="rule-id">{rule.id}</span>
        <span className="badge">{rule.category}</span>
        {label && <span className={`badge ${label.toLowerCase()}`}>{label}</span>}
        <span className="support">
          {rule.support_count} PRs · {rule.distinct_reviewers} reviewers
        </span>
      </div>

      <p className="rule-text">{rule.rule}</p>

      <p className="kv">
        <b>Fires when</b> {rule.trigger}
      </p>
      <p className="kv">
        <b>Why</b> {rule.rationale}
      </p>

      <div className="scopes">
        {rule.scope_paths.map((s) => (
          <span key={s} className="scope">
            {s}
          </span>
        ))}
      </div>

      <details className="evidence">
        <summary>
          Evidence — {rule.evidence.length} review comments across {prs.length} PRs
        </summary>
        <ul>
          {rule.evidence.map((e) => (
            <li key={e.url}>
              <a className="pr" href={e.url} target="_blank" rel="noreferrer">
                PR #{e.pr}
              </a>{' '}
              <span className="path">{e.path}</span>
              <br />
              {e.excerpt}
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
