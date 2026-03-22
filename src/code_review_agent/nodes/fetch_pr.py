"""
fetch_pr node — parses a GitHub PR URL and fetches the diff + metadata via the
GitHub REST API.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import re
import httpx

from code_review_agent.state import ReviewState, PRMetadata


def _parse_pr_url(url: str) -> tuple[str, int]:
    """Return (owner/repo, pr_number) from a GitHub PR URL."""
    match = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if not match:
        raise ValueError(f"Cannot parse PR URL: {url}")
    return match.group(1), int(match.group(2))


def fetch_pr(state: ReviewState, config: RunnableConfig) -> dict:
    """Fetch PR metadata and unified diff from GitHub."""
    github_token = config["configurable"].get("github_token", "")
    pr_url = state["pr_url"]

    repo, pr_number = _parse_pr_url(pr_url)

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    base = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"

    with httpx.Client() as client:
        # PR metadata
        pr_resp = client.get(base, headers=headers)
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        # Unified diff
        diff_resp = client.get(
            base,
            headers={**headers, "Accept": "application/vnd.github.diff"},
        )
        diff_resp.raise_for_status()
        diff_text = diff_resp.text

        # Changed file paths
        files_resp = client.get(f"{base}/files", headers=headers)
        files_resp.raise_for_status()
        changed_files = [f["filename"] for f in files_resp.json()]

    metadata: PRMetadata = {
        "url": pr_url,
        "repo": repo,
        "pr_number": pr_number,
        "title": pr_data["title"],
        "author": pr_data["user"]["login"],
        "base_branch": pr_data["base"]["ref"],
        "head_branch": pr_data["head"]["ref"],
    }

    return {
        "pr_metadata": metadata,
        "diff": diff_text,
        "changed_files": changed_files,
    }
