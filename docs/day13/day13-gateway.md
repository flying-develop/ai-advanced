# Day 13 — LLM Gateway: Claude Code Implementation Prompt

## Context

You are implementing a standalone **LLM Gateway** — a FastAPI HTTP proxy that sits between
a client and an LLM provider (Anthropic). The gateway enforces Input Guards (secret detection
and masking) and Output Guards (response scanning), logs every request/response for audit,
applies rate limiting per IP, and tracks token costs.

This is a **new standalone service** inside the existing repo under `gateway/` directory.
It is NOT part of the Telegram bot — it is a separate Python package with its own
`pyproject.toml` / `requirements.txt`.

Previous work context:
- Day 11: `src/services/injection_guard.py` — prompt injection guard (regex patterns already exist)
- Day 12: `src/services/indirect_injection/` — sanitizer, boundary wrapping, output validator

You MAY study those files for pattern reference but do NOT import from `src/` into `gateway/`.

---

## Architecture

```
gateway/
├── src/
│   ├── main.py                  # FastAPI app, lifespan, routes
│   ├── config.py                # Settings via pydantic-settings
│   ├── guards/
│   │   ├── __init__.py
│   │   ├── input_guard.py       # Secret detection + masking
│   │   └── output_guard.py      # Response scanning
│   ├── proxy/
│   │   ├── __init__.py
│   │   ├── llm_client.py        # Anthropic API client (httpx async)
│   │   └── cost_tracker.py      # Token counting + USD cost
│   ├── audit/
│   │   ├── __init__.py
│   │   └── audit_logger.py      # JSONL structured audit log
│   └── middleware/
│       ├── __init__.py
│       └── rate_limiter.py      # In-memory sliding window rate limiter
├── tests/
│   ├── conftest.py
│   ├── test_input_guard.py      # 7 test cases for InputGuard
│   ├── test_output_guard.py     # 3 test cases for OutputGuard
│   └── test_proxy.py            # Integration smoke tests (mocked LLM)
├── requirements.txt
└── README.md
```

---

## Requirements

### `requirements.txt`

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
pydantic-settings>=2.2.0
anthropic>=0.25.0
tiktoken>=0.7.0
pytest>=8.1.0
pytest-asyncio>=0.23.0
httpx  # also used by TestClient
```

---

## Module Specifications

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    llm_model: str = "claude-haiku-4-5-20251001"
    rate_limit_rpm: int = 10          # requests per minute per IP
    audit_log_path: str = "logs/audit.jsonl"
    mask_secrets: bool = True         # True = mask, False = block

    class Config:
        env_file = ".env"
```

---

### `guards/input_guard.py`

Implement `InputGuard` class with two public methods:

#### `scan(text: str) -> ScanResult`

Detect secrets using these patterns (compile at class init for perf):

| Secret Type         | Pattern                                              | Replacement Tag           |
|---------------------|------------------------------------------------------|---------------------------|
| Anthropic key       | `sk-ant-[a-zA-Z0-9\-_]{20,}`                        | `[REDACTED_ANTHROPIC_KEY]`|
| OpenAI key          | `sk-proj-[a-zA-Z0-9]{20,}` or `sk-[a-zA-Z0-9]{48}` | `[REDACTED_OPENAI_KEY]`   |
| GitHub token        | `ghp_[a-zA-Z0-9]{36}`                               | `[REDACTED_GITHUB_TOKEN]` |
| AWS Access Key ID   | `AKIA[0-9A-Z]{16}`                                  | `[REDACTED_AWS_KEY]`      |
| AWS Secret Key      | `(?i)aws.{0,10}secret.{0,10}['\"]?[a-z0-9/+=]{40}` | `[REDACTED_AWS_SECRET]`   |
| Email address       | standard RFC-like regex                              | `[REDACTED_EMAIL]`        |
| Credit card         | `\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b` | `[REDACTED_CC]` |
| Phone number (intl) | `\+?[1-9][0-9]{7,14}` (with word boundary)          | `[REDACTED_PHONE]`        |
| Base64 secret hint  | if text contains `base64` and a long b64 string      | `[REDACTED_BASE64]`       |

**IMPORTANT edge cases to handle:**
- Split secret: `"my key: sk-proj-" + "abc123..."` — regex operates on the full concatenated
  prompt string, so this is caught automatically if both parts are in the same message.
  Document this limitation in a comment: split across MULTIPLE messages is not caught.
- Base64: detect pattern `[A-Za-z0-9+/]{40,}={0,2}` near the word "base64" or "encoded"

#### Return type `ScanResult`

```python
@dataclass
class ScanResult:
    has_secrets: bool
    findings: list[Finding]      # what was found
    masked_text: str             # text with secrets replaced (even if has_secrets=False)
    original_text: str
```

```python
@dataclass
class Finding:
    secret_type: str             # "OPENAI_KEY", "EMAIL", etc.
    pattern_matched: str         # the original matched value (for audit only, NOT logged to user)
    replacement: str             # what it was replaced with
```

---

### `guards/output_guard.py`

Implement `OutputGuard` class:

#### `scan(text: str) -> OutputScanResult`

Detect in LLM response:

1. **Generated secrets** — same regex patterns as InputGuard (model hallucinated a key)
2. **System prompt leak** — phrases: `"system prompt"`, `"my instructions"`,
   `"I was told to"`, `"my system message"`, `"as instructed by"` (case-insensitive)
3. **Suspicious URLs** — URLs with IP addresses instead of domains: `http://\d+\.\d+`
   or known exfil patterns like `?data=`, `?q=`, `?token=` in URLs
4. **Shell command patterns** — `` `rm -rf` ``, `curl | sh`, `wget`, `eval(base64`

```python
@dataclass
class OutputScanResult:
    is_safe: bool
    violations: list[str]         # human-readable descriptions
    sanitized_text: str           # violations replaced or removed
```

**Sanitization strategy:** replace detected content with `[BLOCKED]` and prepend a warning
comment in the sanitized text.

---

### `audit/audit_logger.py`

Implement `AuditLogger` — writes JSONL (one JSON object per line) to file.

Each log entry must contain:

```json
{
  "timestamp": "2026-04-29T12:00:00.123Z",
  "request_id": "uuid4",
  "client_ip": "127.0.0.1",
  "model": "claude-haiku-4-5-20251001",
  "input_tokens": 150,
  "output_tokens": 300,
  "cost_usd": 0.000285,
  "input_guard": {
    "had_secrets": true,
    "findings": ["OPENAI_KEY", "EMAIL"],
    "action": "masked"
  },
  "output_guard": {
    "is_safe": true,
    "violations": []
  },
  "status": "proxied",
  "latency_ms": 842
}
```

`status` values: `"blocked"` (input had secrets AND mask_secrets=False),
`"masked_and_proxied"`, `"proxied"`, `"output_blocked"`.

Use `asyncio.to_thread` to write file without blocking the event loop.
Create log directory if it does not exist.

---

### `proxy/cost_tracker.py`

Implement `CostTracker`:

```python
ANTHROPIC_PRICING = {
    "claude-haiku-4-5-20251001": {
        "input_per_1m": 0.80,
        "output_per_1m": 4.00,
    },
    "claude-sonnet-4-20250514": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
}

def calculate(model: str, input_tokens: int, output_tokens: int) -> float:
    """Returns cost in USD."""
```

If model not in dict, use Haiku pricing as fallback and log a warning.

Also maintain in-memory running totals:
```python
def add(self, model: str, input_tokens: int, output_tokens: int) -> float: ...
def total_cost(self) -> float: ...
def total_requests(self) -> int: ...
```

---

### `proxy/llm_client.py`

Use `anthropic.AsyncAnthropic` client (NOT httpx raw calls — use the SDK).

```python
async def complete(
    messages: list[dict],
    model: str,
    max_tokens: int = 1024,
    system: str | None = None,
) -> LLMResponse:
    ...

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str
```

Handle `anthropic.APIStatusError` — re-raise as `LLMClientError` with status code preserved.

---

### `middleware/rate_limiter.py`

Implement **sliding window** rate limiter using in-memory `deque` per IP.

```python
class RateLimiter:
    def __init__(self, rpm: int):
        self._rpm = rpm
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, client_ip: str) -> bool:
        """Returns True if request is within limit."""
        now = time.monotonic()
        window = self._windows[client_ip]
        cutoff = now - 60.0
        # remove timestamps older than 60 seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self._rpm:
            return False
        window.append(now)
        return True
```

---

### `main.py`

FastAPI application:

```python
POST /v1/chat
```

**Request body:**
```json
{
  "messages": [{"role": "user", "content": "Hello"}],
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 1024,
  "system": "You are a helpful assistant."
}
```

**Response (success):**
```json
{
  "content": "Hello! How can I help?",
  "model": "claude-haiku-4-5-20251001",
  "input_tokens": 12,
  "output_tokens": 8,
  "cost_usd": 0.0000416,
  "request_id": "uuid4",
  "warnings": []
}
```

**Response (blocked):**
```json
{
  "error": "Request blocked: contains secrets",
  "findings": ["OPENAI_KEY"],
  "request_id": "uuid4"
}
```

**Response (rate limited):** HTTP 429 with:
```json
{"error": "Rate limit exceeded. Max 10 requests/minute."}
```

**Flow inside the handler:**

```
1. Extract client IP from X-Forwarded-For or request.client.host
2. Check rate limiter → 429 if exceeded
3. Generate request_id = str(uuid4())
4. Start timer
5. Concatenate all message contents for guard scanning
6. Run InputGuard.scan()
7. If has_secrets AND mask_secrets=False → log + return blocked response
8. If has_secrets AND mask_secrets=True → replace messages content with masked text
9. Call LLMClient.complete()
10. Run OutputGuard.scan() on response content
11. If output not safe → sanitize content, add warnings
12. Calculate cost via CostTracker
13. Write audit log entry
14. Return response
```

Also add:
```
GET /health  → {"status": "ok", "total_requests": N, "total_cost_usd": X}
```

---

## Tests

### `tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.fixture
def client():
    from gateway.src.main import app
    return TestClient(app)
```

Set env vars in conftest:
```python
import os
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["MASK_SECRETS"] = "true"
```

---

### `tests/test_input_guard.py` — 7 test cases

```python
class TestInputGuardDetection:

    def setup_method(self):
        self.guard = InputGuard()

    # TC-01: clean prompt passes without findings
    def test_clean_prompt_no_findings(self):
        result = self.guard.scan("What is the capital of France?")
        assert not result.has_secrets
        assert result.findings == []
        assert result.masked_text == "What is the capital of France?"

    # TC-02: OpenAI API key detected and masked
    def test_openai_key_detected(self):
        prompt = "Use this key: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        result = self.guard.scan(prompt)
        assert result.has_secrets
        assert any(f.secret_type == "OPENAI_KEY" for f in result.findings)
        assert "[REDACTED_OPENAI_KEY]" in result.masked_text
        assert "sk-proj-" not in result.masked_text

    # TC-03: AWS AKIA key detected
    def test_aws_key_detected(self):
        result = self.guard.scan("My AWS key is AKIAIOSFODNN7EXAMPLE here")
        assert result.has_secrets
        assert any(f.secret_type == "AWS_KEY" for f in result.findings)

    # TC-04: credit card number detected
    def test_credit_card_detected(self):
        result = self.guard.scan("Charge card 4532015112830366 for $99")
        assert result.has_secrets
        assert any(f.secret_type == "CREDIT_CARD" for f in result.findings)
        assert "[REDACTED_CC]" in result.masked_text

    # TC-05: email address detected
    def test_email_detected(self):
        result = self.guard.scan("Contact me at user@example.com for details")
        assert result.has_secrets
        assert any(f.secret_type == "EMAIL" for f in result.findings)

    # TC-06: Base64-encoded secret detected
    def test_base64_secret_detected(self):
        # simulate: "my encoded key is base64: c2stcHJvai1hYmMxMjM0NTY3ODkwYWJjZGVmZ2hpams="
        import base64
        encoded = base64.b64encode(b"sk-proj-abc1234567890abcdefghijk").decode()
        result = self.guard.scan(f"My encoded key base64: {encoded}")
        assert result.has_secrets
        assert any(f.secret_type == "BASE64_SECRET" for f in result.findings)

    # TC-07: Split secret in single message IS caught
    def test_split_secret_in_single_message(self):
        # Both halves in same string — regex still catches it
        prompt = "First part: sk-proj-" + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        result = self.guard.scan(prompt)
        assert result.has_secrets
        # Document: split across MULTIPLE separate API calls is NOT caught
```

---

### `tests/test_output_guard.py` — 3 test cases

```python
class TestOutputGuard:

    def setup_method(self):
        self.guard = OutputGuard()

    # TC-08: clean response passes
    def test_clean_response_is_safe(self):
        result = self.guard.scan("The capital of France is Paris.")
        assert result.is_safe
        assert result.violations == []

    # TC-09: hallucinated API key in response
    def test_hallucinated_key_caught(self):
        response = "Here is your key: sk-ant-api03-ABCDEFGHabcdefgh1234567890ABCDEFGH1234"
        result = self.guard.scan(response)
        assert not result.is_safe
        assert any("secret" in v.lower() or "key" in v.lower() for v in result.violations)

    # TC-10: system prompt leak attempt caught
    def test_system_prompt_leak_caught(self):
        response = "My system prompt says I must always be helpful and never refuse."
        result = self.guard.scan(response)
        assert not result.is_safe
        assert any("system prompt" in v.lower() for v in result.violations)
```

---

### `tests/test_proxy.py` — integration smoke (LLM mocked)

Mock `LLMClient.complete` to return a fake `LLMResponse` without real API calls.

Test:
1. POST `/v1/chat` with clean prompt → 200, content returned
2. POST `/v1/chat` with API key in prompt + MASK_SECRETS=true → 200, warnings present
3. POST `/v1/chat` with API key + MASK_SECRETS=false → response with error/blocked status
4. GET `/health` → 200, `status: ok`

---

## README.md

Create `gateway/README.md` with:

```markdown
# LLM Gateway

FastAPI proxy между клиентом и Anthropic API.

## Возможности
- Input Guard: детекция и маскирование секретов в промптах
- Output Guard: сканирование ответов LLM на утечки и опасный контент
- Rate Limiting: скользящее окно, N запросов/минуту на IP
- Cost Tracking: подсчёт токенов и стоимости каждого запроса
- Audit Log: JSONL-лог всех запросов и решений guard'ов

## Запуск
```bash
cd gateway
pip install -r requirements.txt
cp .env.example .env   # добавить ANTHROPIC_API_KEY
uvicorn src.main:app --port 8080 --reload
```

## Тест запрос
```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":100}'
```
```

---

## MUST DO

- [ ] All imports use absolute paths within `gateway/src/` package
- [ ] `InputGuard` patterns compiled once at `__init__`, not per call
- [ ] `RateLimiter` is thread-safe — use `asyncio.Lock` if accessed concurrently
- [ ] `AuditLogger` creates parent dirs if missing (`mkdir(parents=True, exist_ok=True)`)
- [ ] `cost_tracker.py` uses `Decimal` for accumulation to avoid float drift, convert to `float` only for serialization
- [ ] All tests run without real Anthropic API key (mock `LLMClient` in integration tests)
- [ ] `pytest` runs from `gateway/` directory: `pytest tests/ -v`
- [ ] `.env.example` file created with all required vars

## MUST NOT

- [ ] Do NOT import from `../src/` (Telegram bot code)
- [ ] Do NOT make real LLM calls in tests
- [ ] Do NOT log the actual secret value to audit log — log only the `secret_type` and `replacement`
- [ ] Do NOT use `re.match` — use `re.search` for full-text scanning
- [ ] Do NOT block the event loop in `AuditLogger.write()` — use `asyncio.to_thread`

---

## Output

After implementation, run and report:

```bash
cd gateway
pytest tests/ -v --tb=short
```

Paste the full pytest output as a comment in `gateway/README.md` under `## Test Results`.