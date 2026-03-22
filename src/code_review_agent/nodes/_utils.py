from __future__ import annotations

import json
import re


def parse_json_findings(raw: str) -> list:
    """
    Robustly parse a JSON array from an LLM response.

    Handles:
    - Plain JSON arrays
    - JSON wrapped in ```json ... ``` or ``` ... ``` code fences
    - Leading/trailing prose (extracts the first [...] block)
    """
    if not raw:
        return []

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    # If still not starting with '[', try to find the first array
    if not raw.startswith("["):
        array_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if array_match:
            raw = array_match.group(0)
        else:
            return []

    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []
