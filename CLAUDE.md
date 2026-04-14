# CLAUDE.md — Telegram AI Assistant

## Project Overview

Персональный Telegram-ассистент с AI (LLM) для одного пользователя.
Стек: Python 3.12+, aiogram 3.x, SQLAlchemy 2.x (async), SQLite (aiosqlite), httpx, Anthropic SDK.

---

## Architecture

Трёхслойная архитектура: **Handlers → Services → Repositories**

```
Handler (получает Update от Telegram)
  → вызывает Service (бизнес-логика, оркестрация)
    → Service использует Repository (доступ к данным)
    → Service использует внешние клиенты (LLM API)
  → возвращает ответ пользователю
```

**Принцип**: Handler никогда не содержит бизнес-логику. Service никогда не работает с Telegram API напрямую. Repository — единственная точка доступа к БД.

---

## Project Structure

```
telegram-assistant/
├── CLAUDE.md
├── pyproject.toml
├── alembic.ini
├── .env.example
├── src/
│   ├── __init__.py
│   ├── bot.py                  # Entry point: создание Bot, Dispatcher, запуск
│   ├── config.py               # Pydantic Settings — все переменные окружения
│   ├── di.py                   # Dependency injection — фабрика зависимостей
│   ├── handlers/               # Telegram handlers (thin layer)
│   │   ├── __init__.py         # router registration
│   │   ├── start.py            # /start, /help
│   │   └── assistant.py        # Обработка текстовых сообщений → LLM
│   ├── services/               # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── llm_service.py      # Взаимодействие с LLM API
│   │   └── conversation_service.py  # Управление контекстом диалога
│   ├── repositories/           # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py             # BaseRepository с общими CRUD-операциями
│   │   └── conversation_repo.py
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py             # DeclarativeBase, общие миксины
│   │   └── conversation.py     # Conversation, Message models
│   ├── middlewares/            # aiogram middlewares
│   │   ├── __init__.py
│   │   ├── auth.py             # Проверка ALLOWED_USER_ID
│   │   └── db_session.py       # Инъекция AsyncSession в handler
│   ├── keyboards/              # Reply/Inline keyboards
│   │   └── __init__.py
│   └── utils/                  # Утилиты, хелперы
│       ├── __init__.py
│       └── text.py             # Форматирование, обрезка текста
├── alembic/                    # Миграции БД
│   └── versions/
└── tests/
    ├── conftest.py
    ├── test_services/
    └── test_handlers/
```

---

## Naming Conventions

| Элемент            | Стиль              | Пример                          |
|--------------------|---------------------|---------------------------------|
| Файлы / модули     | snake_case          | `llm_service.py`                |
| Классы             | PascalCase          | `ConversationService`           |
| Функции / методы   | snake_case          | `get_or_create_conversation()`  |
| Константы          | UPPER_SNAKE_CASE    | `MAX_CONTEXT_MESSAGES`          |
| Приватные методы   | _snake_case         | `_build_prompt()`               |
| Pydantic models    | PascalCase + Schema | `MessageSchema`                 |
| SQLAlchemy models  | PascalCase          | `Conversation`                  |
| Handlers           | snake_case          | `handle_message()`              |
| Routers            | snake_case          | `assistant_router`              |

---

## Invariants (НИКОГДА не нарушать)

1. **Handler — тонкий слой**. Handler ТОЛЬКО: парсит входные данные, вызывает service, отправляет ответ. Никакой бизнес-логики, SQL, HTTP-запросов.
2. **Нет прямых SQL-запросов**. Вся работа с БД — через SQLAlchemy ORM и Repository-паттерн.
3. **Конфигурация через `config.py`**. Никаких `os.getenv()` за пределами `config.py`. Используем `pydantic-settings`.
4. **Async everywhere**. Все I/O операции — async/await. Никаких блокирующих вызовов (`requests`, `time.sleep`).
5. **Один пользователь**. Бот персональный — middleware `AuthMiddleware` проверяет `ALLOWED_USER_ID` на каждом апдейте.
6. **Типизация обязательна**. Все функции имеют type hints для аргументов и возвращаемого значения.
7. **Нет `print()`**. Только `logging` модуль через `logger = logging.getLogger(__name__)`.

---

## Patterns & Conventions

### Dependency Injection
Зависимости передаются через аргументы, НЕ через глобальные переменные. В aiogram — через `middleware` → `handler kwargs`.

### Error Handling
- Service-слой выбрасывает кастомные исключения (`LLMServiceError`, `ConversationNotFoundError`)
- Handler ловит и возвращает пользователю человеческое сообщение
- Все неожиданные ошибки логируются с traceback

### Repository Pattern
- Каждая сущность — свой repository
- Repository принимает `AsyncSession` в конструкторе
- Возвращает доменные объекты (модели SQLAlchemy или dataclass)

---

## State Machine (Workflow)

**ОБЯЗАТЕЛЬНО** следовать этому процессу при каждой задаче. Перед каждым переходом — явно указывай текущее и следующее состояние.

```
[IDLE] → получен запрос пользователя
  ↓
[ANALYSIS] — изучить запрос и существующий код
  • Прочитать все затронутые файлы
  • Понять какие слои задеты (handler / service / repository / model)
  • Найти существующие паттерны в аналогичных файлах
  ↓
[PLANNING] — спланировать изменения ПЕРЕД написанием кода
  • Перечислить ВСЕ файлы, которые будут созданы или изменены
  • Для каждого файла — что именно добавляется/меняется
  • Проверить: нужна ли миграция БД? Новые зависимости в di.py? Регистрация роутера?
  ↓
[EXECUTION] — написать код
  • Строго следовать File Template и Naming Conventions
  • Каждый новый файл — по шаблону из секции File Template
  • Порядок создания: model → repository → service → handler → регистрация
  ↓
[VALIDATION] — проверить результат
  • Все ли файлы из PLANNING созданы?
  • Импорты корректны? Нет циклических зависимостей?
  • Type hints на всех функциях?
  • Docstrings на модулях, классах, публичных методах?
  • Handler тонкий? Логика в service?
  • Роутер зарегистрирован в handlers/__init__.py?
  • Middleware/DI обновлены, если нужно?
  ↓
[DONE] — представить результат
  • Список созданных/изменённых файлов
  • Краткое описание что сделано
```

**Правила переходов:**
- Нельзя перейти к EXECUTION без завершённого PLANNING
- Нельзя перейти к DONE без прохождения VALIDATION
- Если VALIDATION выявил проблемы — возврат к EXECUTION

---

## Good Code Examples

### ✅ Example 1: Handler (thin layer)
```python
# src/handlers/assistant.py
from aiogram import Router, types
from src.services.conversation_service import ConversationService

router = Router(name="assistant")


@router.message()
async def handle_message(
    message: types.Message,
    conversation_service: ConversationService,
) -> None:
    """Handle incoming text message — delegate to service."""
    user_text = message.text
    if not user_text:
        return

    response = await conversation_service.get_ai_response(
        user_id=message.from_user.id,
        user_message=user_text,
    )
    await message.answer(response)
```

### ✅ Example 2: Service (business logic)
```python
# src/services/conversation_service.py
import logging
from src.services.llm_service import LLMService
from src.repositories.conversation_repo import ConversationRepository

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        llm_service: LLMService,
        conversation_repo: ConversationRepository,
    ) -> None:
        self._llm = llm_service
        self._repo = conversation_repo

    async def get_ai_response(self, user_id: int, user_message: str) -> str:
        """Process user message: save, build context, call LLM, save response."""
        conversation = await self._repo.get_or_create(user_id=user_id)
        await self._repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )

        context = await self._repo.get_recent_messages(
            conversation_id=conversation.id,
            limit=20,
        )

        try:
            ai_response = await self._llm.complete(messages=context)
        except LLMServiceError:
            logger.exception("LLM request failed for user %s", user_id)
            return "Произошла ошибка при обращении к AI. Попробуй позже."

        await self._repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,
        )
        return ai_response
```

### ✅ Example 3: Repository
```python
# src/repositories/conversation_repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.conversation import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> Conversation:
        """Get active conversation or create new one."""
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation is None:
            conversation = Conversation(user_id=user_id)
            self._session.add(conversation)
            await self._session.flush()

        return conversation
```

### ✅ Example 4: Config
```python
# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    bot_token: str
    allowed_user_id: int
    anthropic_api_key: str

    db_url: str = "sqlite+aiosqlite:///data/bot.db"
    llm_model: str = "claude-sonnet-4-20250514"
    max_context_messages: int = 20


settings = Settings()
```

### ✅ Example 5: Middleware (DI)
```python
# src/middlewares/db_session.py
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker) -> None:
        self._session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self._session_pool() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result
```

---

## Anti-Patterns (ЗАПРЕЩЕНО)

### ❌ Anti-pattern 1: Бизнес-логика в handler
```python
# WRONG — handler делает всё сам
@router.message()
async def handle_message(message: types.Message, session: AsyncSession):
    stmt = select(Conversation).where(Conversation.user_id == message.from_user.id)
    result = await session.execute(stmt)
    conv = result.scalar_one_or_none()
    # ... 30 строк логики прямо в handler
```

### ❌ Anti-pattern 2: os.getenv() вместо config
```python
# WRONG — разбросанные getenv
import os
token = os.getenv("BOT_TOKEN")
api_key = os.getenv("ANTHROPIC_API_KEY")
```

### ❌ Anti-pattern 3: Блокирующие вызовы
```python
# WRONG — requests блокирует event loop
import requests
response = requests.post("https://api.anthropic.com/v1/messages", json=payload)
```

### ❌ Anti-pattern 4: print() вместо logging
```python
# WRONG
print(f"User {user_id} sent message")
print(f"Error: {e}")
```

### ❌ Anti-pattern 5: Отсутствие типизации
```python
# WRONG — нет type hints
async def process(data, flag):
    result = await something(data)
    return result
```

---

## File Template

Каждый новый Python-файл должен следовать этому шаблону:

```python
"""Module description — одна строка, объясняющая назначение модуля."""

# stdlib
import logging
from typing import Optional

# third-party
from sqlalchemy.ext.asyncio import AsyncSession

# local
from src.models.conversation import Conversation
from src.config import settings

logger = logging.getLogger(__name__)


class SomeService:
    """Service description."""

    def __init__(self, dependency: SomeDependency) -> None:
        self._dependency = dependency

    async def do_something(self, param: str) -> str:
        """Method description."""
        ...
```

**Порядок импортов**: stdlib → third-party → local (разделены пустой строкой).
**Docstrings**: обязательны для модулей, классов и публичных методов.

---

## Commands

### /spec-interview
Перед реализацией новой крупной фичи — провести интервью по шаблону `.specs/spec-interview.md`.

---

## Tech Decisions Log

| Решение                    | Почему                                         |
|----------------------------|-------------------------------------------------|
| aiogram 3.x               | Async-first, роутеры, middleware, DI из коробки |
| SQLAlchemy 2.x async      | Лучший ORM для Python, async support            |
| SQLite + aiosqlite         | Персональный бот, не нужен внешний сервер БД    |
| pydantic-settings          | Валидация конфига на старте, .env support        |
| httpx / anthropic SDK      | Async HTTP клиент для LLM API                   |
| alembic                    | Миграции БД — версионирование схемы             |