# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-04-18

### Added
- `/start`, `/help`, `/reset`, `/new_chat`, `/stats`, `/history` commands
- Typing indicator (`ChatAction.TYPING`) while LLM responds
- `split_message()` — paragraph-aware long-message splitting
- Atomic LLM context: user message only saved on success
- `MAX_CONTEXT_MESSAGES` validator (min=1)
- Global error handler via `dp.errors()`
- `py.typed` marker, mypy-clean codebase
- `__all__` in all `__init__.py`
- Full test suite: 41+ tests

### Dependencies
- Python 3.12+, aiogram 3.x, SQLAlchemy 2.x async, pydantic-settings, alembic, httpx
