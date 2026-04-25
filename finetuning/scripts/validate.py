"""Validate a JSONL fine-tuning dataset file for format and schema correctness."""

import json
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    "title", "stack", "level", "salary_from", "currency",
    "remote", "location", "experience_years_min", "experience_years_required",
}
VALID_LEVELS = {"junior", "middle", "senior", "lead", "unknown"}
VALID_REMOTE = {"true", "false", "hybrid", "unknown"}


def validate_file(path: Path) -> tuple[int, list[str]]:
    """Validate JSONL file, return (total_lines, list_of_error_messages)."""
    errors: list[str] = []
    total = 0

    with path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            total += 1

            # 1. Valid JSON
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"Line {lineno}: invalid JSON — {e}")
                continue

            # 2. messages key is a list
            messages = record.get("messages")
            if not isinstance(messages, list):
                errors.append(f"Line {lineno}: 'messages' missing or not a list")
                continue

            # 3. Exactly 3 messages with correct roles
            if len(messages) != 3:
                errors.append(f"Line {lineno}: expected 3 messages, got {len(messages)}")
                continue
            expected_roles = ["system", "user", "assistant"]
            for idx, (msg, role) in enumerate(zip(messages, expected_roles)):
                if msg.get("role") != role:
                    errors.append(f"Line {lineno}: message[{idx}] role is '{msg.get('role')}', expected '{role}'")

            # 4. No content shorter than 10 chars
            for idx, msg in enumerate(messages):
                content = msg.get("content", "")
                if not isinstance(content, str) or len(content) < 10:
                    errors.append(f"Line {lineno}: message[{idx}] content too short or missing")

            # 5. assistant content is valid JSON with required fields
            assistant_content = messages[2].get("content", "")
            try:
                extraction = json.loads(assistant_content)
            except json.JSONDecodeError as e:
                errors.append(f"Line {lineno}: assistant content is not valid JSON — {e}")
                continue

            missing = REQUIRED_FIELDS - set(extraction.keys())
            if missing:
                errors.append(f"Line {lineno}: assistant JSON missing fields: {missing}")
                continue

            # 6. level enum
            if extraction["level"] not in VALID_LEVELS:
                errors.append(f"Line {lineno}: invalid level '{extraction['level']}'")

            # 7. remote enum
            remote_val = str(extraction["remote"]).lower() if extraction["remote"] is not None else "unknown"
            if remote_val not in VALID_REMOTE:
                errors.append(f"Line {lineno}: invalid remote '{extraction['remote']}'")

            # 8. salary_from is number or null (not string)
            sf = extraction["salary_from"]
            if sf is not None and not isinstance(sf, (int, float)):
                errors.append(f"Line {lineno}: salary_from must be number or null, got {type(sf).__name__} '{sf}'")

            # 9. stack is array of strings
            stack = extraction["stack"]
            if not isinstance(stack, list):
                errors.append(f"Line {lineno}: stack must be an array")
            elif any(not isinstance(s, str) for s in stack):
                errors.append(f"Line {lineno}: stack must be an array of strings")

    return total, errors


def main() -> None:
    """Entry point: python scripts/validate.py <file.jsonl>"""
    if len(sys.argv) < 2:
        print("Usage: python finetuning/scripts/validate.py <file.jsonl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    total, errors = validate_file(path)

    print(f"Total lines: {total}")
    print(f"Errors: {len(errors)}")
    for err in errors:
        print(f"  {err}")

    if errors:
        print("FAIL")
        sys.exit(1)
    else:
        print("PASS")


if __name__ == "__main__":
    main()
