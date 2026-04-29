# LLM Gateway

FastAPI proxy между клиентом и Anthropic API.

## Возможности
- **Input Guard**: детекция и маскирование секретов в промптах (API-ключи, email, карты, base64)
- **Output Guard**: сканирование ответов LLM на утечки и опасный контент
- **Rate Limiting**: скользящее окно, N запросов/минуту на IP
- **Cost Tracking**: подсчёт токенов и стоимости каждого запроса (Decimal-аккумулятор)
- **Audit Log**: JSONL-лог всех запросов и решений guard'ов

## Структура

```
gateway/
├── src/
│   ├── main.py               # FastAPI app, lifespan, маршруты
│   ├── config.py             # Settings via pydantic-settings
│   ├── guards/
│   │   ├── input_guard.py    # Детекция и маскирование секретов
│   │   └── output_guard.py   # Сканирование ответов LLM
│   ├── proxy/
│   │   ├── llm_client.py     # Async Anthropic SDK клиент
│   │   └── cost_tracker.py   # Подсчёт стоимости токенов
│   ├── audit/
│   │   └── audit_logger.py   # JSONL-аудит лог
│   └── middleware/
│       └── rate_limiter.py   # In-memory sliding window rate limiter
└── tests/
    ├── conftest.py
    ├── test_input_guard.py   # 7 тест-кейсов
    ├── test_output_guard.py  # 3 тест-кейса
    └── test_proxy.py         # 4 интеграционных теста
```

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

## API

### POST /v1/chat

**Request:**
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

**Response (blocked — MASK_SECRETS=false):**
```json
{
  "error": "Request blocked: contains secrets",
  "findings": ["OPENAI_KEY"],
  "request_id": "uuid4"
}
```

**Response (rate limited):** HTTP 429

### GET /health

```json
{"status": "ok", "total_requests": 5, "total_cost_usd": 0.0042}
```

## Переменные окружения

| Переменная         | По умолчанию                  | Описание                          |
|--------------------|-------------------------------|-----------------------------------|
| `ANTHROPIC_API_KEY`| —                             | Обязательный ключ Anthropic       |
| `LLM_MODEL`        | `claude-haiku-4-5-20251001`   | Модель по умолчанию               |
| `RATE_LIMIT_RPM`   | `10`                          | Лимит запросов/минуту на IP       |
| `AUDIT_LOG_PATH`   | `logs/audit.jsonl`            | Путь к файлу аудит-лога           |
| `MASK_SECRETS`     | `true`                        | true=маскировать, false=блокировать|

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
plugins: asyncio-1.3.0, mock-3.15.1, anyio-4.13.0

gateway/tests/test_input_guard.py::TestInputGuardDetection::test_clean_prompt_no_findings PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_openai_key_detected PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_aws_key_detected PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_credit_card_detected PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_email_detected PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_base64_secret_detected PASSED
gateway/tests/test_input_guard.py::TestInputGuardDetection::test_split_secret_in_single_message PASSED
gateway/tests/test_output_guard.py::TestOutputGuard::test_clean_response_is_safe PASSED
gateway/tests/test_output_guard.py::TestOutputGuard::test_hallucinated_key_caught PASSED
gateway/tests/test_output_guard.py::TestOutputGuard::test_system_prompt_leak_caught PASSED
gateway/tests/test_proxy.py::TestProxyEndpoints::test_clean_prompt_returns_200 PASSED
gateway/tests/test_proxy.py::TestProxyEndpoints::test_masked_secrets_returns_200 PASSED
gateway/tests/test_proxy.py::TestProxyEndpoints::test_blocked_secrets_when_mask_disabled PASSED
gateway/tests/test_proxy.py::TestProxyEndpoints::test_health_endpoint PASSED

============================== 14 passed in 0.36s ==============================
```
