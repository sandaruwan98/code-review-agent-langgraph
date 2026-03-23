"""
reflect node — uses an LLM to critique, deduplicate, and improve the
aggregated findings before they reach the human-approval gate.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import json
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from code_review_agent.state import ReviewState, ReviewComment
from code_review_agent.nodes._utils import parse_json_findings

SYSTEM_PROMPT = """\
You are a staff engineer reviewing a list of automated code-review findings.

Your tasks:
1. Remove exact or near-duplicate findings (keep the most informative one).
2. Upgrade / downgrade severity if a finding is clearly mis-rated.
3. Discard findings that are nitpicks with no real value.
4. Ensure every remaining finding has a concrete, actionable suggestion.

Return the improved list as a JSON array using the SAME schema:
  file, line, severity, category, message, suggestion

Return ONLY the JSON array — no prose.
"""


def reflect(state: ReviewState, config: RunnableConfig) -> dict:
    model_name = config["configurable"].get("model_name", "claude-sonnet-4-6")
    api_key = config["configurable"].get("anthropic_api_key", "")
    base_url = config["configurable"].get("anthropic_base_url", "")

    comments = state.get("final_comments", [])
    if not comments:
        return {"final_comments": []}

    # llm = ChatAnthropic(model=model_name, api_key=api_key, max_tokens=4096)
    llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url, max_tokens=2048)

    user_msg = f"Here are the findings to review:\n\n```json\n{json.dumps(comments, indent=2)}\n```"

    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_msg)]
    )

    raw = response.content.strip()
    parsed = parse_json_findings(raw)
    refined: list[ReviewComment] = parsed if parsed else comments

    usage = response.usage_metadata or {}
    token_usage = state.get("token_usage", {})
    token_usage["reflect"] = {
        "input": usage.get("input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }

    return {"final_comments": refined, "token_usage": token_usage}
