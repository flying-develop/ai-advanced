# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-18

### Added
- `/start` and `/help` commands — welcome message with command list
- `/reset` command — deactivates current conversation so next message starts fresh
- `/new_chat` command — deactivates existing conversation and opens a new one (edge case: no previous conversation handled gracefully)
- `/stats` command — shows total conversation count, message count, and date of first message
- `/history` command — displays last 5 messages from the active conversation with 👤/🤖 role icons
- Plain-text message handling — delegates to `ConversationService` which manages context and calls LLM
- Typing indicator (`ChatAction.TYPING`) shown while LLM generates a response
- Long-message splitting — AI responses longer than 4096 characters are split on paragraph boundaries before sending
- `ConversationService` with atomic message persistence: user message is only saved if LLM succeeds
- `LLMService` — async HTTP client for the Qwen (DashScope) OpenAI-compatible API
- `ConversationRepository` with full CRUD: get-or-create, deactivate, add message, recent messages, stats queries
- SQLAlchemy 2.x async ORM models: `Conversation`, `Message` with `TimestampMixin`
- Alembic migrations for initial schema
- `AuthMiddleware` — blocks all updates from users other than `ALLOWED_USER_ID`
- `DbSessionMiddleware` — injects `AsyncSession` per request, commits on success
- `ServiceInjectMiddleware` — resolves `ConversationService` per request via DI factory
- Global error handler (`dp.errors()`) — logs unhandled exceptions and replies with a safe error message
- `max_context_messages` validation in `Settings` — minimum value of 1 enforced at startup
- LLM response timing logged at INFO level: `LLM response in X.XXs for user_id=...`
- All user-facing strings centralised in `src/utils/messages.py`
- `py.typed` marker for PEP 561 compliance; codebase passes `mypy src/ --ignore-missing-imports`
- `__all__` exports defined in every `__init__.py`
- Comprehensive test suite: 45 tests covering handlers, services, repositories, middlewares, and utilities

### Dependencies
- Python 3.12+
- aiogram 3.x
- SQLAlchemy 2.x (async) + aiosqlite
- pydantic-settings
- alembic
- httpx
