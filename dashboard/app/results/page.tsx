import { getResults, getSaturation, sortCategories } from '@/lib/data';

const ORDER = ['A_baseline', 'B_housestyle', 'C_generic'];

export default function ResultsPage() {
  const results = getResults();
  const saturation = getSaturation();

  return (
    <>
      <h1>Results</h1>

      {!results ? (
        <p className="empty">
          The evaluation has not run yet. Generate <code>eval/results.json</code> with
          Phase 5.
        </p>
      ) : (
        <>
          <p className="lede">
            Scored on <b>{results.held_out_prs} held-out pull requests</b>, fenced off
            before sampling and never mined. Every one qualified at three or more review
            threads, so every one has real human ground truth. A finding matches a comment
            when it is in the same file, within {results.line_window} lines, and the judge
            rules them semantically equivalent ({results.match_rule}).
          </p>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Condition</th>
                  <th style={{ textAlign: 'right' }}>Recall</th>
                  <th style={{ textAlign: 'right' }}>Precision</th>
                  <th style={{ textAlign: 'right' }}>Findings/PR</th>
                  <th style={{ textAlign: 'right' }}>Matched</th>
                </tr>
              </thead>
              <tbody>
                {ORDER.filter((c) => results.conditions[c]).map((c) => {
                  const r = results.conditions[c];
                  return (
                    <tr key={c} className={c === 'B_housestyle' ? 'highlight' : undefined}>
                      <td>
                        <span className="mono">{c}</span>
                        <br />
                        <span style={{ fontSize: 14, color: 'var(--ink-3)' }}>
                          {r.label}
                        </span>
                      </td>
                      <td className="num">{(r.recall * 100).toFixed(1)}%</td>
                      <td className="num">{(r.precision * 100).toFixed(1)}%</td>
                      <td className="num">{r.findings_per_pr}</td>
                      <td className="num">
                        {r.matched} / {r.ground_truth}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <h2>Reading these numbers</h2>
          <p className="note" style={{ marginBottom: 12 }}>
            <b>Precision is measured against what a reviewer actually wrote, which is a
            subset of what they noticed.</b>{' '}
            A correct finding that no human bothered to comment on scores as a false
            positive here. The precision column is a lower bound, and comparing precision
            between conditions says more than any single value.
          </p>
          <p className="note" style={{ marginBottom: 12 }}>
            <b>A_baseline</b> isolates the lift as coming from the mining rather than the
            model — same reviewer, same diffs, no mined rules.
          </p>
          <p className="note">
            <b>C_generic is the ablation.</b> Home Assistant rules applied to Airflow PRs.
            Both are large async Python infrastructure projects, so a C score near B would
            mean the rules are generic Python smells wearing a repository&rsquo;s name.
          </p>

          {ORDER.filter(
            (c) =>
              results.conditions[c] &&
              Object.keys(results.conditions[c].by_category).length > 0,
          ).map((c) => {
            const r = results.conditions[c];
            const cats = sortCategories(Object.keys(r.by_category));
            const max = Math.max(...cats.map((k) => r.by_category[k].findings), 1);
            return (
              <section key={c}>
                <h2>{c} — by category</h2>
                <div className="bars">
                  {cats.map((k) => {
                    const row = r.by_category[k];
                    return (
                      <div className="bar-row" key={k}>
                        <span className="bar-label">{k}</span>
                        <span className="bar-track">
                          <span
                            className="bar-fill muted"
                            style={{ width: `${(row.findings / max) * 100}%` }}
                          >
                            <span
                              className="bar-fill"
                              style={{
                                width: `${
                                  row.findings ? (row.matched / row.findings) * 100 : 0
                                }%`,
                                display: 'block',
                              }}
                            />
                          </span>
                        </span>
                        <span className="bar-value">
                          {row.matched}/{row.findings}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="note" style={{ marginTop: 10, fontSize: 14 }}>
                  Bar length is findings; the filled portion is findings that matched a
                  real human comment.
                </p>
              </section>
            );
          })}
        </>
      )}

      <h2>Rule-discovery saturation</h2>
      {saturation.length === 0 ? (
        <p className="empty">
          No saturation data yet. It accumulates in{' '}
          <code>.bob/rules/airflow-saturation.json</code> as tranches are distilled.
        </p>
      ) : (
        <>
          <p className="note" style={{ marginBottom: 16 }}>
            How much new convention each additional tranche of the corpus buys. When the
            new-rule rate falls below roughly 10%, mining more comments stops paying — that
            is the point at which the rulebook has converged.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tranche</th>
                  <th style={{ textAlign: 'right' }}>Candidates in</th>
                  <th style={{ textAlign: 'right' }}>Rules before</th>
                  <th style={{ textAlign: 'right' }}>Rules after</th>
                  <th style={{ textAlign: 'right' }}>New</th>
                  <th style={{ textAlign: 'right' }}>New-rule rate</th>
                </tr>
              </thead>
              <tbody>
                {saturation.map((s) => (
                  <tr key={s.tranche}>
                    <td className="mono">t{s.tranche}</td>
                    <td className="num">{s.candidates_in}</td>
                    <td className="num">{s.rules_before}</td>
                    <td className="num">{s.rules_after}</td>
                    <td className="num">{s.new_rules}</td>
                    <td className="num">{(s.new_rule_rate * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
