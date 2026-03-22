"""
load_context node — fetches the full content of changed files from GitHub so
the analysis agents have full context, not just the diff hunks.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import httpx

from code_review_agent.state import ReviewState

# Only load files under this size to keep token costs sane
MAX_FILE_BYTES = 50_000


def load_context(state: ReviewState, config: RunnableConfig) -> dict:
    """Fetch raw file content for each changed file."""
    github_token = config["configurable"].get("github_token", "")
    repo = state["pr_metadata"]["repo"]
    head_branch = state["pr_metadata"]["head_branch"]

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    context_files: dict[str, str] = {}

    with httpx.Client() as client:
        for filepath in state["changed_files"]:
            url = f"https://api.github.com/repos/{repo}/contents/{filepath}?ref={head_branch}"
            resp = client.get(url, headers=headers)

            if resp.status_code != 200:
                continue  # file may have been deleted — skip

            content = resp.text
            if len(content.encode()) <= MAX_FILE_BYTES:
                context_files[filepath] = content

    return {"context_files": context_files}
