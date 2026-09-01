/**
 * Reads the generated JSON from disk at build time. No database, no API layer.
 *
 * Every loader tolerates a missing file and returns an empty shape, because the
 * pipeline emits these artifacts in phase order — the dashboard must build against a
 * partially-run pipeline rather than crash on the first absent file.
 */

import fs from 'node:fs';
import path from 'node:path';

const RULES_DIR = path.join(process.cwd(), '..', '.bob', 'rules');
const EVAL_DIR = path.join(process.cwd(), '..', 'eval');

export type Evidence = {
  pr: number;
  url: string;
  path: string;
  excerpt: string;
  signal_strength: string;
};

export type Rule = {
  id: string;
  rule: string;
  category: string;
  trigger: string;
  rationale: string;
  scope_paths: string[];
  support_count: number;
  distinct_reviewers: number;
  evidence: Evidence[];
  kind?: string;
};

export type RuleBook = {
  repo: string;
  generated_at: string;
  support_threshold: number;
  counts: Record<string, number>;
  contested: { a: string; b: string; overlap: number; category: string }[];
  rules: Rule[];
  candidates: Rule[];
  incidents: Rule[];
};

export type CrossCheckLabel = 'CONFIRMED' | 'IMPLIED' | 'TRIBAL';
export type ReverseLabel = 'SUPPORTED' | 'UNSUPPORTED' | 'CONTRADICTED';

export type CrossCheck = {
  repo: string;
  counts: {
    mined_rules: number;
    forward: Partial<Record<CrossCheckLabel, number>>;
    their_rules: number;
    reverse: Partial<Record<ReverseLabel, number>>;
  };
  mined_rules: {
    id: string;
    label: CrossCheckLabel;
    doc_reference?: string;
    why?: string;
    rule?: string;
    category?: string;
    support_count?: number;
  }[];
  their_rules: {
    statement: string;
    source?: string;
    label: ReverseLabel;
    mined_rule_ids?: string[];
    evidence_prs?: number[];
    why?: string;
  }[];
};

export type Saturation = {
  tranche: number;
  batches: number;
  comments_seen?: number;
  candidates_in: number;
  clusters: number;
  rules_before: number;
  rules_after: number;
  new_rules: number;
  new_rule_rate: number;
}[];

export type Results = {
  repo: string;
  generated_at: string;
  held_out_prs: number;
  line_window: number;
  match_rule: string;
  judge: Record<string, unknown>;
  conditions: Record<
    string,
    {
      label: string;
      findings: number;
      ground_truth: number;
      matched: number;
      recall: number;
      precision: number;
      findings_per_pr: number;
      by_category: Record<
        string,
        { findings: number; matched: number; precision: number }
      >;
      top_rules_by_matches: [string, number][];
    }
  >;
};

function readJson<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

const EMPTY_BOOK: RuleBook = {
  repo: '',
  generated_at: '',
  support_threshold: 3,
  counts: {},
  contested: [],
  rules: [],
  candidates: [],
  incidents: [],
};

export function getRuleBook(slug = 'airflow'): RuleBook {
  return readJson(path.join(RULES_DIR, `${slug}-conventions.json`), EMPTY_BOOK);
}

export function getCrossCheck(slug = 'airflow'): CrossCheck | null {
  return readJson<CrossCheck | null>(
    path.join(RULES_DIR, `${slug}-agents-md-crosscheck.json`),
    null,
  );
}

export function getSaturation(slug = 'airflow'): Saturation {
  return readJson<Saturation>(path.join(RULES_DIR, `${slug}-saturation.json`), []);
}

export function getResults(): Results | null {
  return readJson<Results | null>(path.join(EVAL_DIR, 'results.json'), null);
}

/** rule id -> cross-check label, for badges on the rule cards. */
export function getLabels(slug = 'airflow'): Record<string, CrossCheckLabel> {
  const cc = getCrossCheck(slug);
  if (!cc) return {};
  return Object.fromEntries(cc.mined_rules.map((r) => [r.id, r.label]));
}

export function byCategory(rules: Rule[]): Map<string, Rule[]> {
  const out = new Map<string, Rule[]>();
  for (const r of rules) {
    const list = out.get(r.category) ?? [];
    list.push(r);
    out.set(r.category, list);
  }
  return out;
}

export const CATEGORY_ORDER = [
  'correctness',
  'api-design',
  'async',
  'testing',
  'database',
  'security',
  'performance',
  'providers',
  'naming',
  'docs',
  'commit-hygiene',
];

export function sortCategories(cats: string[]): string[] {
  return [...cats].sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a);
    const ib = CATEGORY_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
}
