"""
CLI entry point — run a code review from the terminal.

Usage:
    uv run code-review-agent <PR_URL> [--post] [--min-severity critical|major|minor]
"""
from __future__ import annotations

import argparse
import re
import sys
import textwrap
import uuid

from code_review_agent.config import Settings
from code_review_agent.graph import build_graph

# ── ANSI helpers ─────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
GRAY = "\033[90m"
CYAN = "\033[96m"

SEVERITY_STYLE = {
    "critical": f"{RED}{BOLD}",
    "major": f"{YELLOW}",
    "minor": f"{GRAY}",
}
SEVERITY_EMOJI = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
CATEGORY_EMOJI = {"bug": "🐛", "security": "🔒", "style": "✨", "test": "🧪"}

PR_URL_PATTERN = re.compile(r"github\.com/[^/]+/[^/]+/pull/\d+")

NODE_LABELS = {
    "fetch_pr": "Fetching PR metadata & diff",
    "load_context": "Loading file context",
    "bug_agent": "Analysing for bugs",
    "security_agent": "Analysing for security issues",
    "style_agent": "Analysing for code quality",
    "aggregate": "Aggregating findings",
    "reflect": "Reviewing & deduplicating",
    "human_approval": "Awaiting approval",
    "post_review": "Posting review",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _stream_graph(graph, input_state, config) -> None:
    """Run the graph with streaming, printing per-node progress."""
    for event in graph.stream(input_state, config=config, stream_mode="updates"):
        for node_name in event:
            label = NODE_LABELS.get(node_name, node_name)
            print(f"  {CYAN}→{RESET} {label:.<42s} {GREEN}✓{RESET}")


def _build_config(settings: Settings, args: argparse.Namespace) -> dict:
    """Map Settings + CLI overrides into the configurable dict the graph expects."""
    return {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "anthropic_api_key": settings.anthropic_api_key,
            "anthropic_base_url": settings.anthropic_base_url,
            "model_name": settings.model_name,
            "github_token": settings.github_token,
            "min_severity": args.min_severity or settings.min_severity,
            "post_to_github": args.post or settings.post_to_github,
        }
    }


def _display_findings(comments: list[dict]) -> None:
    """Print findings to the terminal with color and structure."""
    count = len(comments)
    if count == 0:
        print(f"\n{GREEN}No findings — the PR looks clean.{RESET}\n")
        return

    print(f"\n{BOLD}Found {count} finding(s):{RESET}\n")

    for i, c in enumerate(comments, 1):
        sev = c.get("severity", "minor")
        cat = c.get("category", "style")
        style = SEVERITY_STYLE.get(sev, "")
        emoji = SEVERITY_EMOJI.get(sev, "⚪")
        cat_emoji = CATEGORY_EMOJI.get(cat, "💬")

        header = f"  {emoji} {style}{sev.upper()}{RESET}  {cat_emoji} {cat}"
        location = f"{c.get('file', '?')}"
        if c.get("line"):
            location += f":{c['line']}"

        print(f"{DIM}[{i}/{count}]{RESET} {header}  {DIM}{location}{RESET}")

        msg = c.get("message", "")
        print(textwrap.fill(msg, width=80, initial_indent="     ", subsequent_indent="     "))

        suggestion = c.get("suggestion")
        if suggestion:
            print(f"     {CYAN}Suggestion:{RESET}")
            print(textwrap.fill(suggestion, width=80, initial_indent="       ", subsequent_indent="       "))
        print()


def _prompt_approval() -> tuple[bool, str | None]:
    """Interactive approval prompt. Returns (approved, feedback)."""
    print(f"{BOLD}Approve posting this review?{RESET}")
    print("  [y] Yes, post to GitHub")
    print("  [n] No, discard")
    print("  [f] No, but provide feedback")

    while True:
        choice = input(f"\n{BOLD}>{RESET} ").strip().lower()
        if choice in ("y", "yes"):
            return True, None
        if choice in ("n", "no"):
            return False, None
        if choice in ("f", "feedback"):
            feedback = input("Feedback: ").strip()
            return False, feedback or None
        print("  Please enter y, n, or f.")


def _print_token_usage(usage: dict) -> None:
    """Print a summary table of token consumption per node."""
    if not usage:
        return
    print(f"\n{BOLD}Token Usage{RESET}")
    total_in = total_out = 0
    for node, counts in sorted(usage.items()):
        inp = counts.get("input", 0)
        out = counts.get("output", 0)
        total_in += inp
        total_out += out
        print(f"  {node:20s}  in={inp:>6,}  out={out:>6,}")
    print(f"  {DIM}{'─' * 46}{RESET}")
    print(f"  {'TOTAL':20s}  in={total_in:>6,}  out={total_out:>6,}")


# ── Arg parsing ──────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="code-review-agent",
        description="LangGraph-powered agent that reviews GitHub PRs.",
    )
    parser.add_argument("pr_url", metavar="PR_URL", help="GitHub pull request URL")
    parser.add_argument(
        "--post",
        action="store_true",
        default=False,
        help="Actually post the review to GitHub (overrides POST_TO_GITHUB env var)",
    )
    parser.add_argument(
        "--min-severity",
        choices=["critical", "major", "minor"],
        default=None,
        help="Minimum severity to include (overrides MIN_SEVERITY env var)",
    )
    return parser.parse_args(argv)


# ── Main ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    try:
        _run(argv)
    except KeyboardInterrupt:
        print(f"\n{DIM}Aborted.{RESET}")
        sys.exit(130)


def _run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Validate URL early
    if not PR_URL_PATTERN.search(args.pr_url):
        print(f"Error: not a valid GitHub PR URL: {args.pr_url}", file=sys.stderr)
        sys.exit(1)

    # Load settings from .env
    try:
        settings = Settings()
    except Exception as e:
        print(f"Error loading settings from .env: {e}", file=sys.stderr)
        print("Copy .env.example to .env and fill in your API keys.", file=sys.stderr)
        sys.exit(1)

    config = _build_config(settings, args)
    graph = build_graph()

    initial_state = {"pr_url": args.pr_url, "findings": [], "token_usage": {}}

    # Phase 1: run until human_approval interrupt
    print(f"\n{BOLD}Reviewing:{RESET} {args.pr_url}")
    print(f"{DIM}Model: {config['configurable']['model_name']}{RESET}\n")
    try:
        _stream_graph(graph, initial_state, config)
    except Exception as e:
        print(f"\nError during analysis: {e}", file=sys.stderr)
        sys.exit(1)

    # Phase 2: display findings and prompt for approval
    snapshot = graph.get_state(config)
    comments = snapshot.values.get("final_comments", [])
    _display_findings(comments)

    if not comments:
        print(f"{DIM}Nothing to post — exiting.{RESET}")
        _print_token_usage(snapshot.values.get("token_usage", {}))
        return

    approved, feedback = _prompt_approval()

    # Phase 3: resume the graph
    graph.update_state(
        config,
        {"human_approved": approved, "human_feedback": feedback},
        as_node="human_approval",
    )
    _stream_graph(graph, None, config)

    if approved:
        post_mode = "Posted" if config["configurable"]["post_to_github"] else "Dry-run complete"
        print(f"\n{GREEN}{post_mode}.{RESET}")
    else:
        print(f"\n{DIM}Review discarded.{RESET}")

    # Phase 4: token usage summary
    final = graph.get_state(config)
    _print_token_usage(final.values.get("token_usage", {}))
