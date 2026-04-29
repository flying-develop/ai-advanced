"""LLM Gateway — FastAPI application entry point."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gateway.src.audit.audit_logger import AuditLogger
from gateway.src.config import settings
from gateway.src.guards.input_guard import InputGuard
from gateway.src.guards.output_guard import OutputGuard
from gateway.src.middleware.rate_limiter import RateLimiter
from gateway.src.proxy.cost_tracker import CostTracker
from gateway.src.proxy.llm_client import LLMClient, LLMClientError
from gateway.src.proxy.openai_client import OpenAIClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Application state (singletons shared across requests)
# ---------------------------------------------------------------------------

_OPENAI_PREFIXES = ("gpt-", "o1", "o3", "o4")


def _is_openai_model(model: str) -> bool:
    return any(model.startswith(p) for p in _OPENAI_PREFIXES)


class _AppState:
    input_guard: InputGuard
    output_guard: OutputGuard
    rate_limiter: RateLimiter
    anthropic_client: LLMClient
    openai_client: OpenAIClient | None
    cost_tracker: CostTracker
    audit_logger: AuditLogger

    def get_llm_client(self, model: str) -> LLMClient | OpenAIClient:
        if _is_openai_model(model):
            if self.openai_client is None:
                raise LLMClientError("OpenAI API key not configured", status_code=501)
            return self.openai_client
        return self.anthropic_client


state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    state.input_guard = InputGuard()
    state.output_guard = OutputGuard()
    state.rate_limiter = RateLimiter(rpm=settings.rate_limit_rpm)
    state.anthropic_client = LLMClient(api_key=settings.anthropic_api_key)
    state.openai_client = OpenAIClient(api_key=settings.openai_api_key) if settings.openai_api_key else None
    state.cost_tracker = CostTracker()
    state.audit_logger = AuditLogger(log_path=settings.audit_log_path)
    yield


app = FastAPI(title="LLM Gateway", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = settings.llm_model
    max_tokens: int = 1024
    system: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    """Return gateway liveness and running totals."""
    return {
        "status": "ok",
        "total_requests": state.cost_tracker.total_requests(),
        "total_cost_usd": state.cost_tracker.total_cost(),
    }


@app.post("/v1/chat")
async def chat(request: Request, body: ChatRequest) -> JSONResponse:
    """Proxy a chat request through input/output guards to Anthropic."""
    client_ip = _get_client_ip(request)
    request_id = str(uuid4())
    start_time = time.monotonic()

    # 1. Rate limiting
    if not await state.rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": f"Rate limit exceeded. Max {settings.rate_limit_rpm} requests/minute."},
        )

    # 2. Concatenate all message contents for guard scanning
    full_text = "\n".join(m.content for m in body.messages)

    # 3. Input guard
    scan = state.input_guard.scan(full_text)

    input_guard_log: dict[str, Any] = {
        "had_secrets": scan.has_secrets,
        "findings": list({f.secret_type for f in scan.findings}),
        "action": "none",
    }

    if scan.has_secrets and not settings.mask_secrets:
        # Block the request
        input_guard_log["action"] = "blocked"
        latency_ms = int((time.monotonic() - start_time) * 1000)
        await state.audit_logger.write(
            AuditLogger.build_entry(
                request_id=request_id,
                client_ip=client_ip,
                model=body.model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                input_guard_result=input_guard_log,
                output_guard_result={"is_safe": True, "violations": []},
                status="blocked",
                latency_ms=latency_ms,
            )
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "Request blocked: contains secrets",
                "findings": input_guard_log["findings"],
                "request_id": request_id,
            },
        )

    # 4. Build messages for LLM (replace content with masked version if needed)
    messages_for_llm: list[dict] = []
    if scan.has_secrets:
        input_guard_log["action"] = "masked"
        # Replace each message content proportionally using masked full text
        # Simplification: replace the whole concatenated content in the last user message
        # and keep other messages intact.
        for msg in body.messages:
            messages_for_llm.append({"role": msg.role, "content": msg.content})
        # Apply masking to the last user message that triggered it
        # (full re-scan per message would duplicate findings; simpler: mask joined text
        #  then redistribute — here we mask each message individually)
        messages_for_llm = []
        for msg in body.messages:
            masked_msg_scan = state.input_guard.scan(msg.content)
            messages_for_llm.append({"role": msg.role, "content": masked_msg_scan.masked_text})
    else:
        input_guard_log["action"] = "none"
        messages_for_llm = [{"role": m.role, "content": m.content} for m in body.messages]

    # 5. Call LLM (route to Anthropic or OpenAI by model prefix)
    llm_error: LLMClientError | None = None
    llm_response: Any = None
    try:
        llm_client = state.get_llm_client(body.model)
        llm_response = await llm_client.complete(
            messages=messages_for_llm,
            model=body.model,
            max_tokens=body.max_tokens,
            system=body.system,
        )
    except LLMClientError as exc:
        logger.error("LLM request failed: %s", exc)
        llm_error = exc

    # 6. Output guard (only if LLM succeeded)
    out_scan = state.output_guard.scan(llm_response.content) if llm_response else None
    warnings: list[str] = []
    response_content: str = llm_response.content if llm_response else ""

    output_guard_log: dict[str, Any] = {
        "is_safe": out_scan.is_safe if out_scan else True,
        "violations": out_scan.violations if out_scan else [],
    }

    if llm_error:
        final_status = "llm_error"
        cost_usd = 0.0
    elif out_scan and not out_scan.is_safe:
        response_content = out_scan.sanitized_text
        warnings = out_scan.violations
        final_status = "output_blocked"
        cost_usd = state.cost_tracker.add(
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )
    else:
        final_status = "masked_and_proxied" if scan.has_secrets else "proxied"
        cost_usd = state.cost_tracker.add(
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

    # 7. Audit log — always written, even on LLM error
    latency_ms = int((time.monotonic() - start_time) * 1000)
    await state.audit_logger.write(
        AuditLogger.build_entry(
            request_id=request_id,
            client_ip=client_ip,
            model=llm_response.model if llm_response else body.model,
            input_tokens=llm_response.input_tokens if llm_response else 0,
            output_tokens=llm_response.output_tokens if llm_response else 0,
            cost_usd=cost_usd,
            input_guard_result=input_guard_log,
            output_guard_result=output_guard_log,
            status=final_status,
            latency_ms=latency_ms,
        )
    )

    if llm_error:
        return JSONResponse(
            status_code=llm_error.status_code or 502,
            content={"error": str(llm_error), "request_id": request_id},
        )

    return JSONResponse(
        content={
            "content": response_content,
            "model": llm_response.model,
            "input_tokens": llm_response.input_tokens,
            "output_tokens": llm_response.output_tokens,
            "cost_usd": cost_usd,
            "request_id": request_id,
            "warnings": warnings,
        }
    )
