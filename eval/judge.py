#!/usr/bin/env python3
"""
eval/judge.py — semantic-equivalence judge for the A/B/C evaluation.

A generated finding and a human review comment rarely share wording. "Fetch limit+1 rows
so next_cursor can be null on the last page" and "this will return a non-null cursor even
on the final page" are the same review; string overlap says they are not. So matching is
file + line proximity (mechanical) AND semantic equivalence (judged).

Primary judge is **IBM Granite on watsonx.ai**, per the project spec. Every verdict is
cached under ``eval/cache/`` keyed by a hash of the (finding, comment) pair, because this
harness gets re-run and inference should not be re-billed.

A second backend exists because the harness has to be runnable without watsonx
credentials: ``--judge agent`` writes the undecided pairs to a queue file for an agent to
adjudicate with the same rubric, and reads the verdicts back into the same cache. The
cache format is identical either way, so a later watsonx run reuses nothing it should not
and fills in the rest.

Backends:
    watsonx   Granite chat model via the watsonx.ai text/chat API (default)
    agent     emit a queue for an LLM agent, read verdicts back
    cache     cache-only; anything unjudged is reported as unresolved, never guessed

Credentials (from .env):
    WATSONX_API_KEY (or IBM_CLOUD_API_KEY), WATSONX_PROJECT_ID, WATSONX_URL
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx

CACHE_DIR = Path("eval/cache")
QUEUE_PATH = Path("eval/judge_queue.json")

IAM_URL = "https://iam.cloud.ibm.com/identity/token"
DEFAULT_WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
DEFAULT_MODEL = "ibm/granite-3-3-8b-instruct"
API_VERSION = "2024-10-10"

# Out of scope for this hackathon; refuse rather than silently substitute.
BANNED_MODELS = {
    "meta-llama/llama-3-405b-instruct",
    "mistralai/mistral-medium-2505",
    "mistralai/mistral-small-3-1-24b-instruct-2503",
}

VERDICTS = ("MATCH", "PARTIAL", "NO_MATCH")

RUBRIC = """You are judging whether an automated code-review finding refers to the same \
issue as a real human review comment left on the same pull request.

Answer with exactly one verdict, then one sentence of justification.

MATCH     — the finding raises the same concern the human raised, even in different words.
PARTIAL   — related and overlapping (same symptom, or one is a strict subset of the
            other), but they are not asking for the same change.
NO_MATCH  — different concerns that happen to sit near the same lines.

Judge the substance, not the phrasing. Two comments about the same defect are a MATCH \
however differently they are written. Two comments about the same function that ask for \
different changes are NO_MATCH.

Respond in exactly this format:
VERDICT: <MATCH|PARTIAL|NO_MATCH>
WHY: <one sentence>"""


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def pair_key(finding_text: str, comment_text: str, path: str) -> str:
    blob = f"{path}\x00{finding_text.strip()}\x00{comment_text.strip()}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _prompt(finding: dict, comment: dict) -> str:
    return (
        f"FILE: {finding.get('path')}\n\n"
        f"AUTOMATED FINDING (line {finding.get('line')}):\n"
        f"{finding.get('message', '').strip()}\n\n"
        f"HUMAN REVIEW COMMENT (line {comment.get('line')}):\n"
        f"{(comment.get('body') or '').strip()[:2000]}\n"
    )


# ----------------------------------------------------------------------- cache

class VerdictCache:
    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self.dir = cache_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        if key in self._mem:
            return self._mem[key]
        p = self.dir / f"{key}.json"
        if p.exists():
            rec = json.loads(p.read_text(encoding="utf-8"))
            self._mem[key] = rec
            return rec
        return None

    def put(self, key: str, rec: dict) -> None:
        self._mem[key] = rec
        (self.dir / f"{key}.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")

    def __len__(self) -> int:
        return len(list(self.dir.glob("*.json")))


# --------------------------------------------------------------------- watsonx

class WatsonxJudge:
    """IBM Granite chat model via the watsonx.ai text/chat API."""

    def __init__(self, model_id: str | None = None) -> None:
        _load_dotenv()
        self.api_key = os.environ.get("WATSONX_API_KEY") or os.environ.get("IBM_CLOUD_API_KEY", "")
        self.project_id = os.environ.get("WATSONX_PROJECT_ID", "")
        self.url = os.environ.get("WATSONX_URL", DEFAULT_WATSONX_URL).rstrip("/")
        self.model_id = model_id or os.environ.get("WATSONX_MODEL_ID", DEFAULT_MODEL)
        if self.model_id in BANNED_MODELS:
            raise SystemExit(f"model {self.model_id} is out of scope for this hackathon")
        self._token = ""
        self._token_exp = 0.0
        self._client = httpx.Client(timeout=120)

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.project_id)

    def _bearer(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = self._client.post(
            IAM_URL,
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                  "apikey": self.api_key},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_exp = time.time() + body.get("expires_in", 3600)
        return self._token

    def judge(self, finding: dict, comment: dict) -> dict:
        payload = {
            "model_id": self.model_id,
            "project_id": self.project_id,
            "messages": [
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": _prompt(finding, comment)},
            ],
            "max_tokens": 120,
            "temperature": 0,
        }
        r = self._client.post(
            f"{self.url}/ml/v1/text/chat?version={API_VERSION}",
            json=payload,
            headers={"Authorization": f"Bearer {self._bearer()}",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        return {**parse_verdict(text), "judge": f"watsonx:{self.model_id}"}


def parse_verdict(text: str) -> dict:
    verdict, why = "NO_MATCH", ""
    for line in (text or "").splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("VERDICT:"):
            v = up.split(":", 1)[1].strip().strip(".")
            for cand in VERDICTS:
                if cand in v:
                    verdict = cand
                    break
        elif s.upper().startswith("WHY:"):
            why = s.split(":", 1)[1].strip()
    if not why:
        why = (text or "").strip().replace("\n", " ")[:200]
    return {"verdict": verdict, "why": why, "raw": (text or "").strip()[:400]}


# ----------------------------------------------------------------------- queue

def write_queue(pending: list[dict], path: Path = QUEUE_PATH) -> None:
    """Emit undecided pairs for an agent judge, with the rubric inline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "rubric": RUBRIC,
        "instructions": (
            "For each item, decide MATCH, PARTIAL or NO_MATCH by the rubric above and "
            "write eval/judge_verdicts.json as "
            '{"verdicts": [{"key": "<key>", "verdict": "...", "why": "one sentence"}]}. '
            "Every key must appear exactly once. Judge substance, not wording."
        ),
        "n_pending": len(pending),
        "pending": pending,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def ingest_verdicts(path: Path, cache: VerdictCache, judge_name: str = "agent") -> int:
    """Read an agent's verdict file into the shared cache."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("verdicts", data) if isinstance(data, dict) else data
    n = 0
    for row in rows:
        v = str(row.get("verdict", "")).upper().strip()
        if v not in VERDICTS:
            _log(f"  skipping {row.get('key')}: bad verdict {v!r}")
            continue
        cache.put(row["key"], {"verdict": v, "why": row.get("why", ""),
                               "judge": judge_name})
        n += 1
    return n


# ------------------------------------------------------------------- front door

class Judge:
    """Cache-first judge with a pluggable backend."""

    def __init__(self, backend: str = "watsonx", cache_dir: Path = CACHE_DIR) -> None:
        self.backend = backend
        self.cache = VerdictCache(cache_dir)
        self.pending: list[dict] = []
        self.stats = {"cache_hit": 0, "judged": 0, "queued": 0}
        self._wx: WatsonxJudge | None = None
        if backend == "watsonx":
            wx = WatsonxJudge()
            if not wx.available:
                _log("watsonx credentials absent (WATSONX_API_KEY / WATSONX_PROJECT_ID); "
                     "falling back to --judge agent")
                self.backend = "agent"
            else:
                self._wx = wx

    def verdict(self, finding: dict, comment: dict) -> dict | None:
        key = pair_key(finding.get("message", ""), comment.get("body", ""),
                       finding.get("path", ""))
        hit = self.cache.get(key)
        if hit:
            self.stats["cache_hit"] += 1
            return hit
        if self.backend == "watsonx" and self._wx is not None:
            rec = self._wx.judge(finding, comment)
            self.cache.put(key, rec)
            self.stats["judged"] += 1
            return rec
        self.pending.append({
            "key": key,
            "path": finding.get("path"),
            "finding_line": finding.get("line"),
            "finding": finding.get("message", ""),
            "comment_line": comment.get("line"),
            "comment": (comment.get("body") or "")[:2000],
            "comment_url": comment.get("url"),
        })
        self.stats["queued"] += 1
        return None

    def flush_queue(self) -> int:
        if self.pending:
            seen: set[str] = set()
            uniq = []
            for p in self.pending:
                if p["key"] not in seen:
                    seen.add(p["key"])
                    uniq.append(p)
            write_queue(uniq)
            _log(f"{len(uniq)} pairs need judging -> {QUEUE_PATH}")
            return len(uniq)
        return 0
