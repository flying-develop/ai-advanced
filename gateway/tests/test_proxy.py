"""Integration smoke tests for the gateway proxy endpoint (LLM mocked)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.src.proxy.llm_client import LLMResponse

_FAKE_ANTHROPIC_RESPONSE = LLMResponse(
    content="Hello! How can I help?",
    input_tokens=12,
    output_tokens=8,
    model="claude-haiku-4-5-20251001",
    stop_reason="end_turn",
)

_FAKE_OPENAI_RESPONSE = LLMResponse(
    content="Hi there from GPT!",
    input_tokens=10,
    output_tokens=6,
    model="gpt-4o-mini",
    stop_reason="stop",
)

# Keep alias for existing tests
_FAKE_RESPONSE = _FAKE_ANTHROPIC_RESPONSE


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("MASK_SECRETS", "true")


@pytest.fixture
def client():
    from gateway.src.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_no_mask(monkeypatch):
    monkeypatch.setenv("MASK_SECRETS", "false")
    # Reload config so new env var is picked up
    import importlib
    import gateway.src.config as cfg_mod
    importlib.reload(cfg_mod)
    import gateway.src.main as main_mod
    importlib.reload(main_mod)
    with TestClient(main_mod.app) as c:
        yield c
    # Restore
    importlib.reload(cfg_mod)
    importlib.reload(main_mod)


def _mock_llm():
    return patch(
        "gateway.src.main.state.llm_client.complete",
        new_callable=lambda: lambda *a, **kw: AsyncMock(return_value=_FAKE_RESPONSE)(),
    )


class TestProxyEndpoints:

    # Test 1: clean prompt → 200, content returned, no warnings
    def test_clean_prompt_returns_200(self, client):
        with patch("gateway.src.proxy.llm_client.LLMClient.complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = _FAKE_RESPONSE
            response = client.post(
                "/v1/chat",
                json={"messages": [{"role": "user", "content": "Hello, how are you?"}]},
            )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["warnings"] == []
        assert "request_id" in data

    # Test 2: API key in prompt + MASK_SECRETS=true → 200, request goes through
    def test_masked_secrets_returns_200(self, client):
        prompt = "Use this key: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        with patch("gateway.src.proxy.llm_client.LLMClient.complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = _FAKE_RESPONSE
            response = client.post(
                "/v1/chat",
                json={"messages": [{"role": "user", "content": prompt}]},
            )
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        # The masked prompt should NOT appear in forwarded messages — verify mock was called
        assert mock_complete.called
        call_kwargs = mock_complete.call_args
        forwarded_content = call_kwargs[1]["messages"][0]["content"] if call_kwargs[1] else call_kwargs[0][0][0]["content"]
        assert "sk-proj-" not in forwarded_content

    # Test 3: API key in prompt + MASK_SECRETS=false → 400 blocked
    def test_blocked_secrets_when_mask_disabled(self, client_no_mask):
        prompt = "Use this key: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstu"
        response = client_no_mask.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": prompt}]},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "blocked" in data["error"].lower()
        assert "OPENAI_KEY" in data.get("findings", [])

    # Test 4: GET /health → 200, status ok
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "total_requests" in data
        assert "total_cost_usd" in data

    # Test 5: OpenAI model (gpt-4o-mini) → routed to OpenAIClient
    def test_openai_model_routed_correctly(self, client):
        with patch("gateway.src.proxy.openai_client.OpenAIClient.complete", new_callable=AsyncMock) as mock_oai:
            mock_oai.return_value = _FAKE_OPENAI_RESPONSE
            response = client.post(
                "/v1/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello from OpenAI path"}],
                    "model": "gpt-4o-mini",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "gpt-4o-mini"
        assert mock_oai.called

    # Test 6: OpenAI key missing → 501
    def test_openai_model_without_key_returns_501(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        import importlib
        import gateway.src.config as cfg_mod
        importlib.reload(cfg_mod)
        import gateway.src.main as main_mod
        importlib.reload(main_mod)
        with TestClient(main_mod.app) as c:
            response = c.post(
                "/v1/chat",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "gpt-4o-mini",
                },
            )
        assert response.status_code == 501
        importlib.reload(cfg_mod)
        importlib.reload(main_mod)
