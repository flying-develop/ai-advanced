"""Run gpt-4o-mini baseline extraction on 10 eval examples without fine-tuned system prompt."""

import json
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EVAL_FILE = Path("finetuning/data/eval.jsonl")
OUTPUT_FILE = Path("finetuning/data/baseline_results.jsonl")
N_EXAMPLES = 10

BASELINE_SYSTEM = (
    "Extract job vacancy information into JSON with fields: "
    "title, stack, level, salary_from, currency, remote, location, "
    "experience_years_min, experience_years_required"
)


def call_openai_with_retry(client: OpenAI, vacancy_text: str, max_retries: int = 3) -> str:
    """Call gpt-4o-mini baseline with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": BASELINE_SYSTEM},
                    {"role": "user", "content": vacancy_text},
                ],
                temperature=0,
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            wait = 2 ** attempt * 5
            logger.warning("Rate limit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
        except APIError as e:
            wait = 2 ** attempt * 2
            logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")


def load_eval_examples(path: Path, n: int) -> list[dict]:
    """Load first N examples from JSONL file."""
    examples = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
                if len(examples) >= n:
                    break
    return examples


def extract_field(expected: dict, baseline: dict, field: str) -> str:
    """Format field comparison for console output."""
    e = expected.get(field)
    b = baseline.get(field)
    match = "✓" if e == b else "✗"
    return f"  {match} {field}: expected={e!r} baseline={b!r}"


def main() -> None:
    """Run baseline eval and save results."""
    client = OpenAI()
    examples = load_eval_examples(EVAL_FILE, N_EXAMPLES)
    logger.info("Loaded %d eval examples", len(examples))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i, record in enumerate(examples, 1):
        messages = record["messages"]
        vacancy_text = messages[1]["content"]
        expected_str = messages[2]["content"]

        try:
            expected = json.loads(expected_str)
        except json.JSONDecodeError:
            expected = {}

        logger.info("Example %d/%d...", i, len(examples))
        baseline_response = call_openai_with_retry(client, vacancy_text)

        try:
            raw_for_parse = baseline_response.strip()
            if raw_for_parse.startswith("```"):
                # "```json\n{...}\n```" → take the middle part
                inner = raw_for_parse.split("```", 2)[1]
                if inner.startswith("json"):
                    inner = inner[4:]
                raw_for_parse = inner.strip()
            baseline_parsed = json.loads(raw_for_parse)
        except json.JSONDecodeError:
            baseline_parsed = {}

        result = {
            "vacancy_text": vacancy_text[:300] + "..." if len(vacancy_text) > 300 else vacancy_text,
            "expected": expected,
            "baseline_response": baseline_response,
            "notes": "",
        }
        results.append(result)

        print(f"\n{'='*60}")
        print(f"Example {i}/{len(examples)}")
        print(f"{'='*60}")
        fields = ["title", "level", "salary_from", "currency", "remote", "experience_years_min", "experience_years_required"]
        for field in fields:
            print(extract_field(expected, baseline_parsed, field))
        e_stack = set(expected.get("stack") or [])
        b_stack = set(baseline_parsed.get("stack") or [])
        precision = len(e_stack & b_stack) / len(b_stack) if b_stack else 0
        recall = len(e_stack & b_stack) / len(e_stack) if e_stack else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        print(f"  stack F1={f1:.2f} expected={sorted(e_stack)} baseline={sorted(b_stack)}")

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(results)} baseline results → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
