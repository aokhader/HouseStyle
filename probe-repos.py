#!/usr/bin/env python3
"""
probe-repos.py — decide which repo to mine before you spend a single Bobcoin.

Usage:
    export GITHUB_TOKEN=ghp_...        # any classic/fine-grained token, public repo scope
    python3 probe_repos.py

What it measures, per repo:
    human        - of the 100 most recent review comments, how many are from humans (not bots)
    substantive  - how many are >120 chars and not "LGTM"/"nit"/emoji
    med_len      - median human comment length (proxy for how opinionated reviewers are)
    prs          - how many distinct PRs those 100 comments span (low = a few chatty PRs, bad)
    days         - calendar days the 100 comments cover (low = high throughput, good)
    est/month    - rough mineable substantive comments per month

WHAT YOU WANT: substantive > 45, med_len > 150, prs > 25, est/month > 300.
"""

import json
import os
import re
import statistics
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


REPOS = [
    "zulip/zulip",
    "home-assistant/core",
    "autorope/donkeycar",
    "scikit-learn/scikit-learn",
    "pydantic/pydantic",
    "prefecthq/prefect",
    "apache/airflow",
    "supabase/supabase",
]

BOT = re.compile(
    r"(\[bot\]|codecov|dependabot|pre-commit|sonar|coderabbit|greptile|sourcery|renovate)",
    re.I,
)
TRIVIAL = re.compile(r"^\s*(lgtm|nit|thanks?|done|\+1|ok(ay)?|👍|typo|same)\W*$", re.I)

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    sys.exit("Set GITHUB_TOKEN first. Unauthenticated is 60 req/hr and you will hit it.")


def get(url):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "house-style-probe",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def probe(repo):
    url = (
        f"https://api.github.com/repos/{repo}/pulls/comments"
        "?per_page=100&sort=created&direction=desc"
    )
    data = get(url)
    if not data:
        return None

    human = [c for c in data if not BOT.search(c.get("user", {}).get("login", "") or "")]
    subst = [
        c
        for c in human
        if len(c.get("body", "") or "") > 120 and not TRIVIAL.match(c.get("body", "") or "")
    ]
    prs = {c["pull_request_url"].rsplit("/", 1)[-1] for c in data}
    lens = [len(c.get("body", "") or "") for c in human] or [0]

    stamps = sorted(
        datetime.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%SZ") for c in data
    )
    days = max((stamps[-1] - stamps[0]).days, 1)
    per_month = round(len(subst) / days * 30)

    return {
        "human": len(human),
        "substantive": len(subst),
        "med_len": int(statistics.median(lens)),
        "prs": len(prs),
        "days": days,
        "per_month": per_month,
        "newest": stamps[-1].date().isoformat(),
    }


def verdict(m):
    if m is None:
        return "NO DATA"
    score = sum(
        [
            m["substantive"] > 45,
            m["med_len"] > 150,
            m["prs"] > 25,
            m["per_month"] > 300,
        ]
    )
    return {4: "EXCELLENT", 3: "GOOD", 2: "MARGINAL", 1: "WEAK", 0: "REJECT"}[score]


print(
    f"{'repo':28s} {'human':>5s} {'subst':>5s} {'medlen':>6s} "
    f"{'PRs':>4s} {'days':>4s} {'est/mo':>6s}  {'newest':10s}  verdict"
)
print("-" * 96)

for repo in REPOS:
    try:
        m = probe(repo)
    except urllib.error.HTTPError as e:
        print(f"{repo:28s} HTTP {e.code} — {e.reason}")
        continue
    except Exception as e:
        print(f"{repo:28s} ERROR {e}")
        continue

    if m is None:
        print(f"{repo:28s} no review comments found")
        continue

    print(
        f"{repo:28s} {m['human']:5d} {m['substantive']:5d} {m['med_len']:6d} "
        f"{m['prs']:4d} {m['days']:4d} {m['per_month']:6d}  {m['newest']:10s}  {verdict(m)}"
    )
    time.sleep(0.5)

print(
    "\nPick the highest est/mo with med_len > 150. If your top pick spans more than "
    "\n~60 days for 100 comments, widen your harvest window in Phase 1 accordingly."
)