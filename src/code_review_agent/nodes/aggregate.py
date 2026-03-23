"""
aggregate node — merges findings from all parallel analysis branches and
filters by the configured minimum severity.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from code_review_agent.state import ReviewState, ReviewComment

SEVERITY_RANK = {"critical": 3, "major": 2, "minor": 1}


def aggregate(state: ReviewState, config: RunnableConfig) -> dict:
    min_severity = config["configurable"].get("min_severity", "minor")
    min_rank = SEVERITY_RANK.get(min_severity, 1)

    filtered: list[ReviewComment] = [
        f for f in state.get("findings", [])
        if SEVERITY_RANK.get(f.get("severity", "minor"), 1) >= min_rank
    ]

    # Sort: critical first, then by file name for readability
    filtered.sort(
        key=lambda f: (-SEVERITY_RANK.get(f.get("severity", "minor"), 1), f.get("file", ""))
    )

    return {"final_comments": filtered}
