"""
Graph state — the single data structure that flows through every node.
"""
from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict
import operator


class ReviewComment(TypedDict):
    file: str
    line: int | None
    severity: str          # critical | major | minor
    category: str          # bug | security | style | test
    message: str
    suggestion: str | None


class PRMetadata(TypedDict):
    url: str
    repo: str
    pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str


class ReviewState(TypedDict):
    # inputs
    pr_url: str

    # fetched PR data
    pr_metadata: PRMetadata
    diff: str                          # raw unified diff text
    changed_files: list[str]           # file paths touched by the PR
    context_files: dict[str, str]      # filename → file content

    # analysis findings (fan-out nodes append into this list)
    # Annotated with operator.add so parallel branches can write concurrently
    findings: Annotated[list[ReviewComment], operator.add]

    # post-aggregation
    final_comments: list[ReviewComment]  # after reflect / dedup

    # human-in-the-loop
    human_approved: bool
    human_feedback: str | None

