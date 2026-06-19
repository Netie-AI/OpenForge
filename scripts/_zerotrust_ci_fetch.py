#!/usr/bin/env python3
"""Fetch GitHub Actions run/job/step details via REST API (no gh CLI)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = "Netie-AI/OpenForge"
API = f"https://api.github.com/repos/{REPO}/actions/runs"
OUT_DIR = Path("evidence/zerotrust_checkpoint_2026-06-19")


def load_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    env_local = Path("env.local")
    if env_local.exists():
        for line in env_local.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^GITHUB_TOKEN=(.+)$", line.strip())
            if m:
                return m.group(1).strip()
    raise SystemExit("GITHUB_TOKEN not found in environment or env.local")


def api_get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "openforge-zerotrust-ci-fetch",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def format_run_summary(run: dict, jobs_payload: dict) -> str:
    lines = [
        f"run_number: {run.get('run_number')}",
        f"run_id: {run.get('id')}",
        f"url: {run.get('html_url')}",
        f"head_sha: {run.get('head_sha')}",
        f"head_commit_message: {run.get('head_commit', {}).get('message', '').replace(chr(10), ' ')}",
        f"status: {run.get('status')}",
        f"conclusion: {run.get('conclusion')}",
        f"run_started_at: {run.get('run_started_at')}",
        f"updated_at: {run.get('updated_at')}",
        "",
        "jobs:",
    ]
    for j in jobs_payload.get("jobs", []):
        lines.append(
            f"  job: {j.get('name')} status={j.get('status')} conclusion={j.get('conclusion')} "
            f"started={j.get('started_at')} completed={j.get('completed_at')}"
        )
        for s in j.get("steps", []):
            lines.append(f"    step: {s.get('name')} status={s.get('status')} conclusion={s.get('conclusion')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    token = load_token()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    runs_payload = api_get(f"{API}?branch=main&per_page=10", token)
    runs = runs_payload.get("workflow_runs", [])
    if not runs:
        raise SystemExit("No workflow runs returned")

    by_number = {r["run_number"]: r for r in runs}
    targets = [18, 19]
    missing = [n for n in targets if n not in by_number]
    if missing:
        # widen search if #18/#19 not in first page
        runs_payload = api_get(f"{API}?branch=main&per_page=30", token)
        runs = runs_payload.get("workflow_runs", [])
        by_number = {r["run_number"]: r for r in runs}
        missing = [n for n in targets if n not in by_number]
    if missing:
        raise SystemExit(f"Could not find run numbers: {missing}")

    for num in targets:
        run = by_number[num]
        jobs_payload = api_get(f"{API}/{run['id']}/jobs", token)
        text = format_run_summary(run, jobs_payload)
        out_path = OUT_DIR / f"ci_run_{num}_summary.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {out_path} (run_id={run['id']}, conclusion={run.get('conclusion')})")


if __name__ == "__main__":
    main()
