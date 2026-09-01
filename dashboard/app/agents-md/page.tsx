import { getCrossCheck, getRuleBook } from '@/lib/data';

export default function AgentsMdPage() {
  const cc = getCrossCheck('airflow');
  const book = getRuleBook('airflow');

  if (!cc) {
    return (
      <>
        <h1>vs AGENTS.md</h1>
        <p className="empty">
          The cross-check has not run yet. Generate{' '}
          <code>.bob/rules/airflow-agents-md-crosscheck.json</code> with Phase 3.
        </p>
      </>
    );
  }

  const fwd = cc.counts.forward;
  const rev = cc.counts.reverse;
  const fwdTotal = Object.values(fwd).reduce((a, b) => a + (b ?? 0), 0) || 1;
  const revTotal = Object.values(rev).reduce((a, b) => a + (b ?? 0), 0) || 1;
  const unsupported = cc.their_rules.filter((t) => t.label === 'UNSUPPORTED');
  const contradicted = cc.their_rules.filter((t) => t.label === 'CONTRADICTED');
  const byId = new Map(book.rules.map((r) => [r.id, r]));

  return (
    <>
      <h1>Mined rules vs the hand-written AGENTS.md</h1>
      <p className="lede">
        Every team now hand-writes an <code>AGENTS.md</code> full of guessed conventions,
        with no evidence behind any line. Here it is compared against a year of review
        history, in both directions.
      </p>

      <h2>Forward — is each mined rule written down anywhere?</h2>
      <div className="bars" style={{ marginBottom: 10 }}>
        {(['CONFIRMED', 'IMPLIED', 'TRIBAL'] as const).map((l) => (
          <div className="bar-row" key={l}>
            <span className="bar-label">{l}</span>
            <span className="bar-track">
              <span
                className={`bar-fill${l === 'TRIBAL' ? '' : ' muted'}`}
                style={{ width: `${((fwd[l] ?? 0) / fwdTotal) * 100}%` }}
              />
            </span>
            <span className="bar-value">
              {fwd[l] ?? 0} · {(((fwd[l] ?? 0) / fwdTotal) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
      <p className="note">
        <b>CONFIRMED</b> is the correctness check — where the project documented a
        convention, the mining found it independently from review comments alone.{' '}
        <b>TRIBAL is the product</b>: conventions this project enforces in review and has
        never written down.
      </p>

      <h2>Reverse — does review history support each hand-written rule?</h2>
      <div className="bars" style={{ marginBottom: 10 }}>
        {(['SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED'] as const).map((l) => (
          <div className="bar-row" key={l}>
            <span className="bar-label">{l}</span>
            <span className="bar-track">
              <span
                className={`bar-fill${l === 'SUPPORTED' ? ' muted' : ''}`}
                style={{ width: `${((rev[l] ?? 0) / revTotal) * 100}%` }}
              />
            </span>
            <span className="bar-value">
              {rev[l] ?? 0} · {(((rev[l] ?? 0) / revTotal) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
      <p className="note">
        <b>UNSUPPORTED is the argument.</b> These are the hand-written entries that a year
        of review history does not back. They may still be right — a rule so well obeyed it
        never needs stating leaves no trace either — but nobody could tell you which
        without this comparison.
      </p>

      {unsupported.length > 0 && (
        <>
          <h2>Hand-written rules review history does not support</h2>
          <div className="cards">
            {unsupported.map((t, i) => (
              <article className="card" key={i}>
                <div className="card-head">
                  <span className="badge unsupported">UNSUPPORTED</span>
                  {t.source && <span className="rule-id">{t.source}</span>}
                </div>
                <p className="rule-text">{t.statement}</p>
                {t.why && <p className="kv">{t.why}</p>}
              </article>
            ))}
          </div>
        </>
      )}

      {contradicted.length > 0 && (
        <>
          <h2>Contradicted by review history</h2>
          <div className="cards">
            {contradicted.map((t, i) => (
              <article className="card" key={i}>
                <div className="card-head">
                  <span className="badge contradicted">CONTRADICTED</span>
                  {t.source && <span className="rule-id">{t.source}</span>}
                </div>
                <p className="rule-text">{t.statement}</p>
                {t.why && <p className="kv">{t.why}</p>}
                {t.evidence_prs && t.evidence_prs.length > 0 && (
                  <p className="kv mono">
                    {t.evidence_prs.map((n) => `#${n}`).join(', ')}
                  </p>
                )}
              </article>
            ))}
          </div>
        </>
      )}

      <h2>Supported hand-written rules</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Their rule</th>
              <th>Source</th>
              <th>Backed by</th>
            </tr>
          </thead>
          <tbody>
            {cc.their_rules
              .filter((t) => t.label === 'SUPPORTED')
              .map((t, i) => (
                <tr key={i}>
                  <td>{t.statement}</td>
                  <td className="mono">{t.source}</td>
                  <td className="mono">
                    {(t.mined_rule_ids ?? []).map((id) => (
                      <div key={id} title={byId.get(id)?.rule ?? ''}>
                        {id}
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
