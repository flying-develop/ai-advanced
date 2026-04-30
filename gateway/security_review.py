"""Standalone security review script — sends a file to the LLM Gateway and reports findings."""

import json
import sys
from pathlib import Path

import httpx

GATEWAY_URL = "http://localhost:8080/v1/chat"
MODEL = "gpt-4o-mini"
MAX_TOKENS = 1024

_REPO_ROOT = Path(__file__).parent.parent
_PROMPT_PATH = _REPO_ROOT / "docs" / "day14" / "day14-security-prompt.md"

_SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _load_system_prompt() -> str:
    """Read the security review system prompt from docs/."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _load_target(filepath: str) -> tuple[str, str]:
    """Return (resolved_path_str, file_contents). Exits with code 2 on error."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}")
        sys.exit(2)
    return str(path), path.read_text(encoding="utf-8")


def _call_gateway(system_prompt: str, filepath: str, code: str) -> str:
    """POST to the gateway and return the raw content string."""
    user_content = f"Review this code:\n\n{filepath}\n\n{code}"
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    try:
        response = httpx.post(GATEWAY_URL, json=payload, timeout=60)
    except httpx.ConnectError:
        print("Gateway unavailable at localhost:8080")
        sys.exit(2)

    if response.status_code != 200:
        print(f"Gateway returned {response.status_code}:")
        print(response.text)
        sys.exit(2)

    return response.json()["content"]


def _parse_result(raw: str) -> dict:
    """Strip optional ```json fences and parse JSON. Exits with code 2 on failure."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence line and closing fence line
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("Failed to parse JSON response from gateway:")
        print(raw)
        sys.exit(2)


def _print_results(result: dict, filepath: str) -> None:
    """Pretty-print findings, summary, and verdict."""
    findings: list[dict] = result.get("findings", [])
    findings_sorted = sorted(
        findings,
        key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "Low"), 99),
    )

    for f in findings_sorted:
        severity = f.get("severity", "?")
        line = f.get("line")
        issue = f.get("issue", "")
        fix = f.get("fix", "")
        line_str = f"Line {line}" if line is not None else "Line ?"
        print(f"[{severity}] {line_str}: {issue}")
        print(f"Fix: {fix}")
        print()

    print(f"Summary: {result.get('summary', '')}")
    print(f"Verdict: {result.get('verdict', 'UNKNOWN')}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python gateway/security_review.py <path_to_file>")
        sys.exit(2)

    target_arg = sys.argv[1]

    print(f"Security review: {target_arg}")
    print(f"Gateway: {GATEWAY_URL}")
    print("-" * 40)

    system_prompt = _load_system_prompt()
    filepath, code = _load_target(target_arg)
    raw = _call_gateway(system_prompt, filepath, code)
    result = _parse_result(raw)

    _print_results(result, filepath)

    verdict = result.get("verdict", "")
    sys.exit(1 if verdict == "FAIL" else 0)


if __name__ == "__main__":
    main()
