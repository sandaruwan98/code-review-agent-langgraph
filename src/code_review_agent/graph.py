"""
graph.py — assembles the LangGraph StateGraph for the code review agent.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import sqlite3
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

DB_PATH = Path(__file__).resolve().parents[2] / "checkpoints.db"

from code_review_agent.state import ReviewState
from code_review_agent.nodes import (
    fetch_pr,
    load_context,
    bug_agent,
    security_agent,
    style_agent,
    aggregate,
    reflect,
    post_review,
)


def human_approval(state: ReviewState) -> dict:
    """
    Human-in-the-loop interrupt node.
    LangGraph will pause here when .invoke() is called with an interrupt.
    The caller resumes by calling .invoke() again with updated state fields:
      human_approved=True/False and optionally human_feedback="..."
    """
    # This node itself is a no-op — the interrupt happens via graph config.
    # We just return the approval fields that were injected by the human.
    return {
        "human_approved": state.get("human_approved", False),
        "human_feedback": state.get("human_feedback"),
    }


def should_post(state: ReviewState) -> str:
    """Conditional edge: proceed to post_review only if human approved."""
    if state.get("human_approved", False):
        return "post_review"
    return END


def build_graph(checkpointer=None):
    builder = StateGraph(ReviewState)

    # ── nodes ────────────────────────────────────────────────────────────────
    builder.add_node("fetch_pr", fetch_pr)
    builder.add_node("load_context", load_context)
    builder.add_node("bug_agent", bug_agent)
    builder.add_node("security_agent", security_agent)
    builder.add_node("style_agent", style_agent)
    builder.add_node("aggregate", aggregate)
    builder.add_node("reflect", reflect)
    builder.add_node("human_approval", human_approval)
    builder.add_node("post_review", post_review)

    # ── edges ─────────────────────────────────────────────────────────────────
    builder.add_edge(START, "fetch_pr")
    builder.add_edge("fetch_pr", "load_context")

    # Fan-out: all three analysis agents run in parallel
    builder.add_edge("load_context", "bug_agent")
    builder.add_edge("load_context", "security_agent")
    builder.add_edge("load_context", "style_agent")

    # Fan-in: aggregate waits for all three
    builder.add_edge("bug_agent", "aggregate")
    builder.add_edge("security_agent", "aggregate")
    builder.add_edge("style_agent", "aggregate")

    builder.add_edge("aggregate", "reflect")
    builder.add_edge("reflect", "human_approval")

    # Conditional: human approved → post, else end
    builder.add_conditional_edges("human_approval", should_post)
    builder.add_edge("post_review", END)

    cp = checkpointer or SqliteSaver(sqlite3.connect(str(DB_PATH), check_same_thread=False))
    return builder.compile(checkpointer=cp, interrupt_before=["human_approval"])
