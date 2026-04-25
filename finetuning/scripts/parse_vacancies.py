"""Parse real job vacancies from vacancies.txt and extract structured data via gpt-4o-mini."""

import json
import logging
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VACANCIES_FILE = Path("docs/day6/vacancies.txt")
OUTPUT_FILE = Path("finetuning/data/real_examples.jsonl")

SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. Extract job vacancy information "
    "into a strict JSON format. Always return valid JSON only, no explanation."
)

EXTRACTION_PROMPT = """Extract the following fields from the job vacancy text:

{
  "title": "job title (string)",
  "stack": ["array of specific technologies/tools/languages/frameworks — no soft skills"],
  "level": "junior | middle | senior | lead | unknown",
  "salary_from": <minimum salary as a number or null — take exactly as written, do not convert>,
  "currency": "RUB | USD | EUR | null",
  "remote": "true | false | hybrid | unknown",
  "location": "city/location string or null",
  "experience_years_min": <minimum years required as a number or null>,
  "experience_years_required": "normal | inflated | unknown"
}

Rules:
- experience_years_required: 'inflated' if requirements are clearly above market (e.g. 6+ years for a role where 2-3 suffice with AI tools). 'normal' if adequate. 'unknown' if unclear.
- salary_from: minimum of the range exactly as stated (e.g. 350000 for "350 000 – 500 000 ₽"). null if not specified.
- stack: only concrete technologies, languages, frameworks, tools — never soft skills.
- level: infer from job title, required experience, and responsibilities combined.

Return only valid JSON, no markdown, no explanation.

Vacancy text:
"""

HH_ARTIFACTS = re.compile(
    r"Смотрят сейчас\s*\n\s*\d+\s*\n?"
    r"|Опубликована\s*\n\s*[\d.]+\s*\n?"
    r"|и еще \d+\s*"
    r"|·\s*\n"
    r"|\n·\s*",
    re.MULTILINE,
)

METRO_LINE = re.compile(r"^\s*[А-ЯЁ][а-яё]+(?:ская|ская|ово|ая|евская|цкая|инская|ная)\s*$", re.MULTILINE)


def clean_vacancy(text: str) -> str:
    """Remove hh.ru technical artifacts from vacancy text."""
    text = HH_ARTIFACTS.sub("\n", text)
    text = METRO_LINE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def call_openai_with_retry(client: OpenAI, vacancy_text: str, max_retries: int = 3) -> str:
    """Call gpt-4o-mini with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": EXTRACTION_PROMPT + vacancy_text},
                ],
                temperature=0,
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except RateLimitError:
            wait = 2 ** attempt * 5
            logger.warning("Rate limit hit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
        except APIError as e:
            wait = 2 ** attempt * 2
            logger.warning("API error: %s, waiting %ds (attempt %d/%d)", e, wait, attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")


def make_record(vacancy_text: str, extraction_json: str) -> dict:
    """Build a JSONL messages record."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": vacancy_text},
            {"role": "assistant", "content": extraction_json.strip()},
        ]
    }


def main() -> None:
    """Parse vacancies.txt and save real_examples.jsonl."""
    client = OpenAI()

    raw = VACANCIES_FILE.read_text(encoding="utf-8")
    vacancies = [v.strip() for v in raw.split("\n---\n") if v.strip()]
    logger.info("Found %d vacancies in %s", len(vacancies), VACANCIES_FILE)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    saved = 0
    errors = 0
    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for i, raw_vac in enumerate(vacancies, 1):
            cleaned = clean_vacancy(raw_vac)
            if len(cleaned) < 50:
                logger.warning("Vacancy %d too short after cleaning, skipping", i)
                continue
            try:
                extraction = call_openai_with_retry(client, cleaned)
                json.loads(extraction)  # validate JSON
                record = make_record(cleaned, extraction)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                saved += 1
                logger.info("Vacancy %d/%d done", i, len(vacancies))
            except json.JSONDecodeError:
                logger.error("Vacancy %d: extraction is not valid JSON, skipping", i)
                errors += 1
            except Exception as e:
                logger.error("Vacancy %d: %s", i, e)
                errors += 1

    print(f"Saved: {saved} real examples → {OUTPUT_FILE}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
