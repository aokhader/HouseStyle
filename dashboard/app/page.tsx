import { RuleBrowser } from '@/components/RuleBrowser';
import { getLabels, getRuleBook, sortCategories } from '@/lib/data';

export default function RulesPage() {
  const book = getRuleBook('airflow');
  const labels = getLabels('airflow');
  const categories = sortCategories([...new Set(book.rules.map((r) => r.category))]);
  const tribal = Object.values(labels).filter((l) => l === 'TRIBAL').length;

  if (book.rules.length === 0) {
    return (
      <>
        <h1>Rules</h1>
        <p className="empty">
          No rulebook yet. Run the Phase 2 distillation to generate{' '}
          <code>.bob/rules/airflow-conventions.json</code>.
        </p>
      </>
    );
  }

  return (
    <>
      <h1>Mined conventions</h1>
      <p className="lede">
        Distilled from review comments on merged pull requests. A pattern becomes a rule at{' '}
        <b>{book.support_threshold} distinct supporting PRs</b>; below that it stays a
        candidate. Support counts are computed from the harvested corpus, never asserted by
        a model — evidence whose permalink does not resolve to a real comment is dropped
        rather than counted.
      </p>

      <div className="stat-row">
        <div className="stat">
          <div className="n">{book.counts.rules_promoted ?? book.rules.length}</div>
          <div className="k">rules</div>
        </div>
        {tribal > 0 && (
          <div className="stat is-accent">
            <div className="n">{tribal}</div>
            <div className="k">tribal</div>
          </div>
        )}
        <div className="stat">
          <div className="n">{book.counts.candidates_in ?? 0}</div>
          <div className="k">candidates in</div>
        </div>
        <div className="stat">
          <div className="n">{book.counts.rules_candidate ?? book.candidates.length}</div>
          <div className="k">below threshold</div>
        </div>
        <div className="stat">
          <div className="n">{book.counts.incidents ?? book.incidents.length}</div>
          <div className="k">incidents</div>
        </div>
        <div className="stat">
          <div className="n">{book.contested.length}</div>
          <div className="k">contested</div>
        </div>
      </div>

      {book.contested.length > 0 && (
        <>
          <h2>Contested</h2>
          <p className="note" style={{ marginBottom: 14 }}>
            Rule pairs with overlapping triggers in the same scope. Flagged, never silently
            merged — a human decides which one the repo actually means.
          </p>
          <ul className="plain" style={{ marginBottom: 8 }}>
            {book.contested.map((c) => (
              <li key={`${c.a}-${c.b}`} className="note">
                <code>{c.a}</code> vs <code>{c.b}</code> — trigger overlap {c.overlap} (
                {c.category})
              </li>
            ))}
          </ul>
        </>
      )}

      <h2>Rulebook</h2>
      <RuleBrowser rules={book.rules} labels={labels} categories={categories} />
    </>
  );
}
