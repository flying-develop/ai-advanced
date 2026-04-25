"""Merge real and synthetic examples, shuffle, and split 80/20 into train/eval sets."""

import json
import logging
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("finetuning/data")
REAL_FILE = DATA_DIR / "real_examples.jsonl"
SYNTHETIC_FILE = DATA_DIR / "synthetic_examples.jsonl"
ALL_FILE = DATA_DIR / "all_examples.jsonl"
TRAIN_FILE = DATA_DIR / "train.jsonl"
EVAL_FILE = DATA_DIR / "eval.jsonl"

RANDOM_SEED = 42
TRAIN_RATIO = 0.8


def load_jsonl(path: Path, source_tag: str) -> list[dict]:
    """Load JSONL file and tag each record with its source."""
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                record = json.loads(line)
                record["_source"] = source_tag
                records.append(record)
    return records


def write_jsonl(records: list[dict], path: Path, strip_source: bool = True) -> None:
    """Write records to JSONL, optionally stripping internal _source tag."""
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            if strip_source:
                record = {k: v for k, v in record.items() if k != "_source"}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    """Merge, shuffle, and split dataset."""
    real = load_jsonl(REAL_FILE, "real")
    synthetic = load_jsonl(SYNTHETIC_FILE, "synthetic")
    logger.info("Loaded: %d real, %d synthetic", len(real), len(synthetic))

    all_records = real + synthetic
    random.seed(RANDOM_SEED)
    random.shuffle(all_records)

    write_jsonl(all_records, ALL_FILE)
    logger.info("Saved %d total examples → %s", len(all_records), ALL_FILE)

    split_idx = int(len(all_records) * TRAIN_RATIO)
    train = all_records[:split_idx]
    eval_ = all_records[split_idx:]

    write_jsonl(train, TRAIN_FILE)
    write_jsonl(eval_, EVAL_FILE)

    real_in_train = sum(1 for r in train if r["_source"] == "real")
    real_in_eval = sum(1 for r in eval_ if r["_source"] == "real")

    print(f"Real examples:      {len(real)}")
    print(f"Synthetic examples: {len(synthetic)}")
    print(f"Total:              {len(all_records)}")
    print(f"Train ({TRAIN_RATIO:.0%}):         {len(train)} ({real_in_train} real, {len(train)-real_in_train} synthetic)")
    print(f"Eval  ({1-TRAIN_RATIO:.0%}):         {len(eval_)} ({real_in_eval} real, {len(eval_)-real_in_eval} synthetic)")


if __name__ == "__main__":
    main()
