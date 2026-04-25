# Fine-tuning Dataset Pipeline

Dataset creation and fine-tuning pipeline for structured extraction from job vacancies.

## Setup

```bash
pip install openai python-dotenv
# Ensure OPENAI_API_KEY is set in .env
```

## Usage

Run from project root (`ai-advanced/`):

```bash
# Task 1 — parse real vacancies (docs/day6/vacancies.txt → 40 examples)
python finetuning/scripts/parse_vacancies.py

# Task 2 — generate 80+ synthetic examples
python finetuning/scripts/generate_synthetic.py

# Task 3 — merge + shuffle + 80/20 split
python finetuning/scripts/merge_split.py

# Task 4 — validate datasets
python finetuning/scripts/validate.py finetuning/data/train.jsonl
python finetuning/scripts/validate.py finetuning/data/eval.jsonl

# Task 5 — baseline evaluation (first 10 eval examples)
python finetuning/scripts/baseline.py

# Task 6 — fine-tune client (dry run only, don't auto-run)
python finetuning/scripts/finetune_client.py --file finetuning/data/train.jsonl --dry-run
```

## Output Files

| File | Description |
|------|-------------|
| `data/real_examples.jsonl` | ~40 examples from real hh.ru vacancies |
| `data/synthetic_examples.jsonl` | 80+ generated examples |
| `data/all_examples.jsonl` | merged + shuffled |
| `data/train.jsonl` | 80% split |
| `data/eval.jsonl` | 20% split |
| `data/baseline_results.jsonl` | baseline eval results |
| `data/baseline_criteria.md` | evaluation criteria |

## Extraction Schema

```json
{
  "title": "string",
  "stack": ["array of technologies"],
  "level": "junior | middle | senior | lead | unknown",
  "salary_from": "number or null",
  "currency": "RUB | USD | EUR | null",
  "remote": "true | false | hybrid | unknown",
  "location": "string or null",
  "experience_years_min": "number or null",
  "experience_years_required": "normal | inflated | unknown"
}
```
