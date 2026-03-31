"""
post_review node — posts the final comments to the GitHub PR as a review.
Skipped when POST_TO_GITHUB is False (dry-run mode).
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import httpx

from code_review_agent.state import ReviewState, ReviewComment

SEVERITY_EMOJI = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
CATEGORY_EMOJI = {"bug": "🐛", "security": "🔒", "style": "✨", "test": "🧪"}


def _format_comment(c: ReviewComment) -> str:
    sev = SEVERITY_EMOJI.get(c.get("severity", "minor"), "⚪")
    cat = CATEGORY_EMOJI.get(c.get("category", "style"), "💬")
    lines = [
        f"{sev} **{c.get('severity', '').upper()}** {cat} `{c.get('category', '')}`",
        "",
        c.get("message", ""),
    ]
    if c.get("suggestion"):
        lines += ["", f"**Suggestion:** {c['suggestion']}"]
    return "\n".join(lines)


def post_review(state: ReviewState, config: RunnableConfig) -> dict:
    post_to_github = config["configurable"].get("post_to_github", False)

    if not post_to_github:
        print("\n[dry-run] Would post the following review:\n")
        for c in state.get("final_comments", []):
            print(_format_comment(c))
            print("---")
        return {}

    github_token = config["configurable"].get("github_token", "")
    repo = state["pr_metadata"]["repo"]
    pr_number = state["pr_metadata"]["pr_number"]

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Build review body summary
    comments = state.get("final_comments", [])
    summary_lines = [
        "## Automated Code Review",
        f"Found **{len(comments)}** finding(s).",
        "",
    ]
    for c in comments:
        summary_lines.append(f"- {_format_comment(c)}")

    body = "\n".join(summary_lines)

    with httpx.Client() as client:
        resp = client.post(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
            headers=headers,
            json={"body": body, "event": "COMMENT"},
        )
        resp.raise_for_status()

    return {}
