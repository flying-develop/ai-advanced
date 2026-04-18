# Промпты для Прогона 3 — qwen2.5-coder:7b (Continue.dev)

Рабочая ветка: `day5-local-model`  
Путь к worktree: `/tmp/local-run`  
Открой `/tmp/local-run` в IDE и прогони 5–7 задач ниже через Continue.dev.

После каждой задачи:
1. `pytest tests/ -v` — должен быть зелёный
2. `git add -A && git commit -m "[local] #N описание"`
3. Запиши результат в `tasks/execution-log.md` (секция Прогон 3)

---

## Задача #2 — typing indicator

**Файл:** `src/handlers/assistant.py`

```
Добавь `await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)`
перед вызовом conversation_service.get_ai_response().
Импортируй: from aiogram.enums import ChatAction
```

**Критерий:** handler отправляет typing action перед LLM-вызовом.

---

## Задача #3 — split_message

**Файл:** `src/utils/text.py`

```
Добавь функцию split_message(text: str, max_len: int = 4096) -> list[str].
Разбивай по абзацам (двойной перенос строки), не режь слова посередине.
Если текст <= max_len — возвращай [text].
```

**Файл:** `src/handlers/assistant.py`

```
Импортируй split_message из src.utils.text.
Замени `await message.answer(response)` на:
    for part in split_message(response):
        await message.answer(part)
```

**Критерий:** функция в text.py, тест на разбивку, handler использует её.

---

## Задача #5 — LLM ошибка ломает контекст

**Файл:** `src/services/conversation_service.py`

```
Сейчас: user-сообщение сохраняется в БД ДО вызова LLM.
При ошибке LLM — user msg остаётся в контексте, следующий запрос "дырявый".

Исправь: не сохраняй user-сообщение заранее.
Вместо этого — передавай его в LLM как временный объект Message (не через session.add).
Сохраняй оба сообщения (user + assistant) только ПОСЛЕ успешного ответа LLM.
```

**Критерий:** при ошибке LLM user-сообщение НЕ сохраняется. Тест.

---

## Задача #11 — MAX_CONTEXT_MESSAGES=0

**Файл:** `src/config.py`

```
Добавь валидатор для max_context_messages: минимальное значение = 1.
Используй @field_validator("max_context_messages") из pydantic.
При значении < 1 — raise ValueError("max_context_messages must be at least 1").
```

**Критерий:** Settings(max_context_messages=0) бросает ValidationError. Тест.

---

## Задача #12 — /history

**Файлы:** `src/repositories/conversation_repo.py`, `src/services/conversation_service.py`, `src/handlers/history.py`

```
Команда /history — показывает последние 5 сообщений текущего диалога.
Формат:
👤 текст пользователя
🤖 ответ ассистента

1. Repo: метод get_last_messages_for_user(user_id, limit=5) -> list[Message]
2. Service: метод get_history(user_id, limit=5) -> list[dict]
3. Handler: /history, тонкий слой, форматирует и отвечает
4. Зарегистрируй роутер в handlers/__init__.py и bot.py
```

**Критерий:** handler + service + repo-метод, форматированный вывод.

---

## (бонус) Задача #13 — docstrings

**Файлы:** `src/services/conversation_service.py`, `src/services/llm_service.py`

```
Добавь docstrings на все публичные методы в формате:
    """Одна строка.

    Args:
        param: описание.

    Returns:
        описание.

    Raises:
        ExceptionType: когда.
    """
```

---

## После прогона — заполни в execution-log.md:

```markdown
## Прогон 3 — Локальная модель (qwen2.5-coder:7b, Continue.dev)

| # | Задача | Тип | Результат | Примечание |
|---|--------|-----|-----------|-----------|
| 2 | typing indicator | feature | ✅/⚠️/❌ | |
| 3 | split_message | feature | ✅/⚠️/❌ | |
| 5 | LLM ошибка | bugfix | ✅/⚠️/❌ | |
| 11 | MAX_CONTEXT_MESSAGES=0 | bugfix | ✅/⚠️/❌ | |
| 12 | /history | feature | ✅/⚠️/❌ | |

### Метрики
- Задач завершено: _/5
- Тестов до / после: 33 / ___
- С первого раза: _/5
- Где сломалось: #___ — причина: ___
```
