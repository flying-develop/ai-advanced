# Execution Log — День 5

## Прогон 1 — Claude Code (облако)

| # | Задача | Тип | Результат | Коммит | Примечание |
|---|--------|-----|-----------|--------|-----------|
| 1 | /new_chat edge case | bugfix | ✅ | — | Уже реализовано в day4: handler → NEW_CHAT_NO_PREVIOUS, тест существует |
| 2 | typing indicator | feature | ✅ | 5c27795 | ChatAction.TYPING перед вызовом LLM |
| 3 | split_message | feature | ✅ | 2df0ec4 | split_message() по абзацам, 8 тестов, handler использует |
| 4 | строковые константы | refactor | ✅ | — | Уже реализовано в day4: messages.py |
| 5 | LLM ошибка ломает контекст | bugfix | ✅ | 688d4dd | Атомарное сохранение, тест: user msg не сохраняется при ошибке |
| 6 | /stats | feature | ✅ | — | Уже реализовано в day4 |
| 7 | логирование времени LLM | feature | ✅ | — | Уже реализовано в day4 |
| 8 | mypy clean | refactor | ✅ | 8519302 | py.typed, assert-guards, 0 ошибок |
| 9 | __all__ экспорты | refactor | ✅ | 7926c71 | Все __init__.py получили __all__ |
| 10 | глобальный error handler | refactor | ✅ | f645865 | dp.errors() с логгированием и ответом пользователю |
| 11 | MAX_CONTEXT_MESSAGES=0 | bugfix | ✅ | 1ad81fc | field_validator, минимум 1, 3 теста |
| 12 | /history | feature | ✅ | e0fdca7 | handler + service + repo, 👤/🤖 иконки |
| 13 | docstrings на services/ | docs | ✅ | df849e7 | Args/Returns/Raises на всех публичных методах |
| 14 | CHANGELOG.md | docs | ✅ | d8469b8 | Keep a Changelog, v0.1.0 |
| 15 | ADR-001 aiogram | docs | ✅ | e611657 | Context/Decision/Consequences |

### Метрики
- **Подряд без вмешательства:** 15/15
- **На какой задаче сломался:** не сломался
- **Задач, уже выполненных в day3-4:** 4 (#1, #4, #6, #7)
- **Новых коммитов:** 11
- **Тестов до / после:** 33 → 45 (+12)
- **С первого раза (%):** 15/15 = 100% (одна итерация починки в #3: empty string)

---

## Прогон 2 — Claude Code (повторный аудит и доработка)

Доработки после Прогона 1:
- Перенесён inline-импорт `MessageModel` на уровень модуля (#5)
- Добавлены `/stats` и `/history` в `HELP_TEXT` (#12)
- Добавлены тесты для `/history` handler + service (#12)
- Добавлен тест для multi-part send при длинном ответе (#3)
- Добавлен smoke-тест `/new_chat` без предшествующего диалога (#1)

| # | Задача | Тип | Результат | Примечание |
|---|--------|-----|-----------|-----------|
| 1 | /new_chat edge case | bugfix | ✅ | Добавлен smoke-тест handler-уровня |
| 2 | typing indicator | feature | ✅ | Без изменений |
| 3 | split_message | feature | ✅ | Добавлен тест multi-part send |
| 4 | строковые константы | refactor | ✅ | Без изменений |
| 5 | LLM ошибка ломает контекст | bugfix | ✅ | Inline import → module level |
| 6 | /stats | feature | ✅ | Добавлено в HELP_TEXT |
| 7 | логирование времени LLM | feature | ✅ | Без изменений |
| 8 | mypy clean | refactor | ✅ | Без изменений |
| 9 | __all__ экспорты | refactor | ✅ | Без изменений |
| 10 | глобальный error handler | refactor | ✅ | Без изменений |
| 11 | MAX_CONTEXT_MESSAGES=0 | bugfix | ✅ | Без изменений |
| 12 | /history | feature | ✅ | Добавлено в HELP_TEXT, +6 тестов |
| 13 | docstrings на services/ | docs | ✅ | Без изменений |
| 14 | CHANGELOG.md | docs | ✅ | Без изменений |
| 15 | ADR-001 aiogram | docs | ✅ | Без изменений |

### Сравнение П1 vs П2

| Метрика | Прогон 1 | Прогон 2 |
|---------|---------|---------|
| Подряд без вмешательства | 15/15 | 15/15 |
| С первого раза (%) | 100% | 100% |
| Тестов после прогона | 45 | 53 (+8) |
| mypy errors | 0 | 0 |
| Пропущенных gap'ов | 4 (HELP_TEXT, inline import, /history tests, split test) | 0 |

---

## Прогон 3 — Claude Code (глубокий аудит)

Доработки после Прогона 2:
- Обнаружено нарушение инварианта #4: `"Произошла внутренняя ошибка."` хардкод в `bot.py` → вынесен в `messages.py` как `INTERNAL_ERROR_MESSAGE`
- Удалена мёртвая функция `split_long_message` (не экспортировалась, нигде не использовалась)
- Добавлен `[tool.mypy]` в `pyproject.toml` — теперь `mypy src/` работает без флагов
- Добавлен тест на typing indicator: `send_chat_action` вызывается с `ChatAction.TYPING`
- `_make_message()` в тестах дополнен `chat` и `bot` атрибутами

| # | Задача | Тип | Результат | Примечание |
|---|--------|-----|-----------|-----------|
| 4 | строковые константы | refactor | ✅+ | Нарушение инварианта в bot.py исправлено: `INTERNAL_ERROR_MESSAGE` |
| 2 | typing indicator | feature | ✅+ | Добавлен тест `test_typing_indicator_sent_before_llm_call` |
| 3 | split_message | feature | ✅+ | Удалена мёртвая `split_long_message` |
| 8 | mypy clean | refactor | ✅+ | `[tool.mypy]` в pyproject.toml, `mypy src/` без флагов |
| 1–15 | все остальные | — | ✅ | Без изменений |

### Сравнение П1 → П2 → П3

| Метрика | Прогон 1 | Прогон 2 | Прогон 3 |
|---------|---------|---------|---------|
| Тестов | 45 | 53 | **54** |
| mypy errors | 0 | 0 | **0** |
| Инвариантов нарушено | 1 (скрытый) | 1 (скрытый) | **0** |
| Мёртвого кода | 1 функция | 1 функция | **0** |
| Пропущенных gap'ов | 4 | 0 | **0** |

---

## Прогон 3 — Облачная модель на свежей ветке `day5-local-model`

Ветка: `day5-local-model` от `badef5c` (состояние после day4, до day5)  
Worktree: `/tmp/local-run`  
Тестов на старте: 33

| # | Задача | Тип | Результат | Коммит | Примечание |
|---|--------|-----|-----------|--------|-----------|
| 1 | /new_chat edge case | bugfix | ✅ | — | Уже в day4 |
| 2 | typing indicator | feature | ✅ | c8c4576 | |
| 3 | split_message | feature | ✅ | 2e3309b | 5 тестов |
| 4 | строковые константы | refactor | ✅ | — | Уже в day4 |
| 5 | LLM ошибка | bugfix | ✅ | 5b26e94 | атомарное сохранение |
| 6 | /stats | feature | ✅ | — | Уже в day4 |
| 7 | LLM timing | feature | ✅ | — | Уже в day4 |
| 8 | mypy clean | refactor | ✅ | 2c75d20 | py.typed, 0 errors |
| 9 | __all__ | refactor | ✅ | 030cdcc | |
| 10 | error handler | refactor | ✅ | 8fd7042 | dp.errors() |
| 11 | MAX_CONTEXT=0 | bugfix | ✅ | 56d0c6a | 2 теста |
| 12 | /history | feature | ✅ | ec632e0 | handler+service+repo |
| 13 | docstrings | docs | ✅ | d2c2d06 | |
| 14 | CHANGELOG.md | docs | ✅ | d2c2d06 | |
| 15 | ADR-001 | docs | ✅ | d2c2d06 | |

### Метрики
- **Тестов:** 33 → 41 (+8)
- **mypy:** 0 errors
- **Коммитов:** 9
- **С первого раза:** 15/15 = 100%
