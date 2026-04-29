"""JSONL-based audit logger for all gateway requests and guard decisions."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditLogger:
    """Writes one JSON object per line to an audit log file (non-blocking)."""

    def __init__(self, log_path: str) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def write(self, entry: dict) -> None:
        """Append one audit entry to the JSONL file without blocking the event loop."""
        line = json.dumps(entry, default=str) + "\n"
        await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

    @staticmethod
    def build_entry(
        *,
        request_id: str,
        client_ip: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        input_guard_result: dict,
        output_guard_result: dict,
        status: str,
        latency_ms: int,
    ) -> dict:
        """Construct a structured audit log entry."""
        return {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "request_id": request_id,
            "client_ip": client_ip,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "input_guard": input_guard_result,
            "output_guard": output_guard_result,
            "status": status,
            "latency_ms": latency_ms,
        }
