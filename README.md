# Telegram AI Assistant

Персональный Telegram-бот с AI-ассистентом на базе Claude (Anthropic API).

## Стек

- **Python 3.12+**
- **aiogram 3.x** — async Telegram Bot framework
- **SQLAlchemy 2.x** (async) + **aiosqlite** — ORM и SQLite
- **Anthropic SDK** — интеграция с Claude API
- **pydantic-settings** — конфигурация через `.env`
- **Alembic** — миграции БД

## Возможности

- Диалог с AI-ассистентом (Claude) прямо в Telegram
- Сохранение истории диалогов с контекстом
- Управление диалогами (`/new_chat` — начать новый)
- Авторизация по user_id (персональный бот)

## Быстрый старт

```bash
# Клонировать репозиторий
git clone <repo-url>
cd telegram-assistant

# Установить зависимости
pip install -e .

# Скопировать и заполнить конфиг
cp .env.example .env
# Заполнить: BOT_TOKEN, ALLOWED_USER_ID, ANTHROPIC_API_KEY

# Применить миграции
alembic upgrade head

# Запустить бота
python -m src.bot
```

## Переменные окружения

| Переменная           | Описание                        | Обязательная |
|----------------------|---------------------------------|:------------:|
| `BOT_TOKEN`          | Токен Telegram-бота (@BotFather)| ✅           |
| `ALLOWED_USER_ID`    | Telegram ID владельца бота      | ✅           |
| `ANTHROPIC_API_KEY`  | API-ключ Anthropic              | ✅           |
| `DB_URL`             | URL базы данных                 | ❌ (default: sqlite) |
| `LLM_MODEL`          | Модель Claude                   | ❌ (default: claude-sonnet-4-20250514) |
| `MAX_CONTEXT_MESSAGES` | Кол-во сообщений в контексте  | ❌ (default: 20) |

## Архитектура

```
Handlers (thin layer) → Services (business logic) → Repositories (data access)
```

Подробнее — см. [CLAUDE.md](CLAUDE.md).

## Команды бота

| Команда      | Описание                              |
|--------------|---------------------------------------|
| `/start`     | Приветствие и краткая справка         |
| `/help`      | Список доступных команд              |
| `/new_chat`  | Начать новый диалог (сбросить контекст)|

## Структура проекта

```
src/
├── bot.py              # Точка входа
├── config.py           # Конфигурация (pydantic-settings)
├── di.py               # Dependency injection
├── handlers/           # Telegram handlers
├── services/           # Бизнес-логика
├── repositories/       # Data access layer
├── models/             # SQLAlchemy модели
├── middlewares/         # Auth, DB session
├── keyboards/          # Клавиатуры
└── utils/              # Утилиты
```

## Разработка

```bash
# Создать миграцию после изменения моделей
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head
```

## Лицензия

MIT