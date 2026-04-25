"""
Fine-tune client for OpenAI API.
Stages: upload file → create job → poll status

NOT for automatic execution. Prepare code only.
"""

import argparse
import logging
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class FineTuneClient:
    """Client for managing OpenAI fine-tuning jobs."""

    def __init__(self) -> None:
        self._client = OpenAI()

    def upload_file(self, filepath: str) -> str:
        """Upload JSONL file for fine-tuning, return file_id."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        logger.info("Uploading %s (%d bytes)...", path, path.stat().st_size)
        with path.open("rb") as f:
            response = self._client.files.create(file=f, purpose="fine-tune")
        file_id = response.id
        logger.info("Uploaded: file_id=%s", file_id)
        return file_id

    def create_job(
        self,
        file_id: str,
        model: str = "gpt-4o-mini-2024-07-18",
        suffix: str = "vacancy-extraction",
    ) -> str:
        """Create a fine-tune job, return job_id."""
        logger.info("Creating fine-tune job: model=%s suffix=%s file_id=%s", model, suffix, file_id)
        response = self._client.fine_tuning.jobs.create(
            training_file=file_id,
            model=model,
            suffix=suffix,
        )
        job_id = response.id
        logger.info("Job created: job_id=%s status=%s", job_id, response.status)
        return job_id

    def poll_status(self, job_id: str, interval_seconds: int = 30) -> dict:
        """Poll job status every N seconds until completion or failure."""
        logger.info("Polling job %s every %ds...", job_id, interval_seconds)
        while True:
            job = self._client.fine_tuning.jobs.retrieve(job_id)
            status = job.status
            logger.info("Job %s: status=%s", job_id, status)
            if status in ("succeeded", "failed", "cancelled"):
                if status == "succeeded":
                    logger.info("Fine-tuned model: %s", job.fine_tuned_model)
                else:
                    logger.error("Job %s finished with status: %s", job_id, status)
                return {
                    "job_id": job_id,
                    "status": status,
                    "fine_tuned_model": job.fine_tuned_model,
                    "trained_tokens": job.trained_tokens,
                }
            time.sleep(interval_seconds)

    def run_full_pipeline(self, train_file: str) -> None:
        """Run upload → create → poll — full cycle with logging."""
        logger.info("=== Fine-tune pipeline start ===")
        file_id = self.upload_file(train_file)
        job_id = self.create_job(file_id)
        result = self.poll_status(job_id)
        logger.info("=== Pipeline complete: %s ===", result)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="OpenAI fine-tune client")
    parser.add_argument("--file", required=True, help="Path to train.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, do not call API")
    parser.add_argument("--model", default="gpt-4o-mini-2024-07-18", help="Base model to fine-tune")
    parser.add_argument("--suffix", default="vacancy-extraction", help="Fine-tuned model name suffix")
    args = parser.parse_args()

    if args.dry_run:
        path = Path(args.file)
        lines = sum(1 for _ in path.open(encoding="utf-8")) if path.exists() else 0
        print("DRY RUN — would do:")
        print(f"  1. Upload {args.file} ({lines} training examples)")
        print(f"  2. Create fine-tune job: model={args.model} suffix={args.suffix}")
        print("  3. Poll status every 30s until succeeded/failed")
        print(f"  4. Resulting model name: {args.model}:{args.suffix}")
        return

    client = FineTuneClient()
    client.run_full_pipeline(args.file)


if __name__ == "__main__":
    main()
