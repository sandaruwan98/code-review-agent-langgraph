"""
style_agent node — analyses the diff for code quality issues and test coverage
gaps (combined into one agent to save cost).
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from code_review_agent.state import ReviewState, ReviewComment
from code_review_agent.nodes._utils import parse_json_findings

SYSTEM_PROMPT = """\
You are a senior software engineer performing a code review focused on
CODE QUALITY and TEST COVERAGE.

Analyse the provided unified diff and file context. Look for:

Code Quality:
- Functions / classes that are too large or doing too much
- Duplicated logic that should be extracted
- Misleading variable / function names
- Missing or inadequate comments on complex logic
- Unnecessary complexity or over-engineering

Test Coverage:
- New public functions / methods with no corresponding tests
- Missing edge-case tests (empty input, boundary values, error paths)
- Tests that assert too little (no meaningful assertions)

Return a JSON array of findings. Each item must have these exact keys:
  file, line (integer or null), severity (critical|major|minor),
  category ("style" or "test"), message, suggestion

Return [] if you find no issues. Return ONLY the JSON array — no prose.
"""


def style_agent(state: ReviewState, config: RunnableConfig) -> dict:
    model_name = config["configurable"].get("model_name", "claude-sonnet-4-6")
    api_key = config["configurable"].get("anthropic_api_key", "")
    base_url = config["configurable"].get("model_base_url", "")

    # llm = ChatAnthropic(model=model_name, api_key=api_key, max_tokens=2048)
    llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url, max_tokens=2048)

    context_snippet = "\n\n".join(
        f"### {fname}\n```\n{content[:3000]}\n```"
        for fname, content in state.get("context_files", {}).items()
    )

    user_msg = f"""
## Diff
```diff
{state['diff'][:6000]}
```

## File Context
{context_snippet or '(no additional context)'}
"""

    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_msg)]
    )

    raw = response.content.strip()
    findings: list[ReviewComment] = parse_json_findings(raw)

    usage = response.usage_metadata or {}
    token_usage = state.get("token_usage", {})
    token_usage["style_agent"] = {
        "input": usage.get("input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }

    return {"findings": findings, "token_usage": token_usage}
