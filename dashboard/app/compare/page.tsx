import { getRuleBook, sortCategories } from '@/lib/data';

export default function ComparePage() {
  const airflow = getRuleBook('airflow');
  const hass = getRuleBook('hass');

  if (airflow.rules.length === 0 || hass.rules.length === 0) {
    return (
      <>
        <h1>Compare</h1>
        <p className="empty">
          Both rulebooks are needed here. Missing:{' '}
          <code>
            {airflow.rules.length === 0
              ? '.bob/rules/airflow-conventions.json'
              : '.bob/rules/hass-conventions.json'}
          </code>
          .
        </p>
      </>
    );
  }

  const cats = sortCategories([
    ...new Set([
      ...airflow.rules.map((r) => r.category),
      ...hass.rules.map((r) => r.category),
    ]),
  ]);

  const count = (rules: { category: string }[], c: string) =>
    rules.filter((r) => r.category === c).length;

  return (
    <>
      <h1>Two repositories, two rulebooks</h1>
      <p className="lede">
        <code>{airflow.repo}</code> and <code>{hass.repo}</code> are both large async
        Python infrastructure projects with strict CI and a big contributor base. If mined
        conventions were really just generic Python smells, these two lists would look
        alike. Read any category row across and they do not.
      </p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th style={{ textAlign: 'right' }}>{airflow.repo}</th>
              <th style={{ textAlign: 'right' }}>{hass.repo}</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c}>
                <td className="mono">{c}</td>
                <td className="num">{count(airflow.rules, c)}</td>
                <td className="num">{count(hass.rules, c)}</td>
              </tr>
            ))}
            <tr className="highlight">
              <td>total</td>
              <td className="num">{airflow.rules.length}</td>
              <td className="num">{hass.rules.length}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>The rules themselves</h2>
      <p className="note" style={{ marginBottom: 18 }}>
        The five highest-support rules from each. The takeaway should land in about three
        seconds: these are not two dialects of one rulebook, they are two different
        rulebooks.
      </p>

      <div className="split">
        <div>
          <p className="col-head">{airflow.repo}</p>
          <ul className="plain">
            {airflow.rules.slice(0, 5).map((r) => (
              <li className="card" key={r.id}>
                <div className="card-head">
                  <span className="rule-id">{r.id}</span>
                  <span className="badge">{r.category}</span>
                  <span className="support">{r.support_count} PRs</span>
                </div>
                <p className="rule-text" style={{ fontSize: 15.5 }}>
                  {r.rule}
                </p>
                <div className="scopes">
                  {r.scope_paths.slice(0, 2).map((s) => (
                    <span className="scope" key={s}>
                      {s}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="col-head">{hass.repo}</p>
          <ul className="plain">
            {hass.rules.slice(0, 5).map((r) => (
              <li className="card" key={r.id}>
                <div className="card-head">
                  <span className="rule-id">{r.id}</span>
                  <span className="badge">{r.category}</span>
                  <span className="support">{r.support_count} PRs</span>
                </div>
                <p className="rule-text" style={{ fontSize: 15.5 }}>
                  {r.rule}
                </p>
                <div className="scopes">
                  {r.scope_paths.slice(0, 2).map((s) => (
                    <span className="scope" key={s}>
                      {s}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <h2>Why this matters for the evaluation</h2>
      <p className="note">
        The Home Assistant rulebook is also condition <b>C</b> in the A/B/C evaluation:
        these rules are applied to Airflow pull requests. It is the ablation. If C scored
        near B, the mining would be detecting generic Python smells rather than one
        repository&rsquo;s house style, and the whole premise would be empty.
      </p>
    </>
  );
}
