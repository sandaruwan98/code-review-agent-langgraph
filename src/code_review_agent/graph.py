"""
graph.py — assembles the LangGraph StateGraph for the code review agent.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from code_review_agent.state import ReviewState
from code_review_agent.nodes import (
    fetch_pr,
    load_context,
    bug_agent,
    security_agent,
    style_agent,
    aggregate,
    reflect
)

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
    builder.add_edge("reflect", END)

    cp = checkpointer or MemorySaver()
    return builder.compile(checkpointer=cp)
