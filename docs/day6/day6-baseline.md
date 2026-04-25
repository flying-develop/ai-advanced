# День 6 — Dataset для Fine-tuning: Extraction из вакансий

## Контекст

Задача: обучить модель извлекать структурированные данные из текстов вакансий (русских и английских).

Реальные данные: файл `vacancies.txt` — вакансии разделены строкой `---`.

## Схема извлечения

Каждый пример должен извлекать следующие поля:

```json
{
  "title": "название должности (строка)",
  "stack": ["массив технологий/инструментов"],
  "level": "junior | middle | senior | lead | unknown",
  "salary_from": "число или null (минимальная зарплата как указана в вакансии)",
  "currency": "RUB | USD | EUR | null",
  "remote": "true | false | hybrid | unknown",
  "location": "строка или null",
  "experience_years_min": "число или null (берём ровно то что написано в вакансии)",
  "experience_years_required": "normal | inflated | unknown"
}
```

### Правила заполнения полей

- `experience_years_required`: `inflated` — если требования явно завышены относительно реального рынка (например, 6+ лет для роли где 2-3 года достаточно с AI-инструментами). `normal` — если требования адекватны. `unknown` — если невозможно определить.
- `salary_from`: берём минимум из диапазона как написано, не интерпретируем. Если зарплата не указана — `null`.
- `stack`: только конкретные технологии, языки, фреймворки, инструменты — не мягкие навыки.
- `level`: определяем по совокупности признаков (название, опыт, обязанности), не только по слову в названии.

## Задача 1 — Парсинг реальных вакансий

1. Прочитай файл `vacancies.txt`
2. Разбей по разделителю `---` на отдельные вакансии
3. Очисти каждую: убери технические артефакты hh.ru ("Смотрят сейчас", "Опубликована", адреса метро, "и еще N")
4. Для каждой вакансии сформируй JSONL-запись в формате:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a structured data extraction assistant. Extract job vacancy information into a strict JSON format. Always return valid JSON only, no explanation."
    },
    {
      "role": "user",
      "content": "<текст вакансии>"
    },
    {
      "role": "assistant",
      "content": "<JSON с извлечёнными полями>"
    }
  ]
}
```

5. Сохрани реальные примеры в `data/real_examples.jsonl`

## Задача 2 — Генерация синтетических вакансий

Используй OpenAI API (gpt-4o-mini) для генерации синтетических примеров.

Нужно покрыть разнообразие:
- Уровни: junior, middle, senior, lead
- Зарплата: указана в RUB, в USD, не указана
- Remote: полностью удалённо, гибрид, только офис
- Стек: Python/ML, PHP/Backend, JS/Frontend, DevOps, Data Science
- Язык вакансии: русский и английский (50/50)
- Граничные случаи: зарплата размытая ("обсуждается"), опыт противоречивый, стек не указан

### Промпт для генерации синтетики

```
Generate a realistic job vacancy text for a {role} position.
Requirements:
- Language: {lang}
- Level: {level}  
- Salary: {salary_instruction}
- Remote: {remote}
- Stack: {stack}
- Length: 150-400 words
- Style: realistic Russian/international job board posting

Then provide the correct JSON extraction for this vacancy following this schema:
{schema}

Return as JSON: {"vacancy_text": "...", "extraction": {...}}
```

Генерируй батчами по 10, сохраняй в `data/synthetic_examples.jsonl`.

**Цель: минимум 80 синтетических примеров** (итого с реальными — 100+).

## Задача 3 — Объединение и сплит

1. Объедини `real_examples.jsonl` + `synthetic_examples.jsonl` → `data/all_examples.jsonl`
2. Перемешай (random seed=42)
3. Раздели 80/20:
   - `data/train.jsonl` — 80%
   - `data/eval.jsonl` — 20%
4. Выведи статистику: сколько примеров в каждом файле, сколько реальных vs синтетических

## Задача 4 — Скрипт валидации

Создай `scripts/validate.py`:

```
Проверяет JSONL файл на корректность.

Проверки:
1. Каждая строка — валидный JSON
2. Есть ключ "messages" — массив
3. Ровно 3 сообщения: system, user, assistant
4. Ни одно content не пустое и не короче 10 символов
5. assistant content — валидный JSON с обязательными полями схемы
6. Поле "level" — одно из допустимых значений
7. Поле "remote" — одно из допустимых значений
8. "salary_from" — число или null (не строка)
9. "stack" — массив строк

Вывод:
- Общее количество строк
- Количество ошибок с описанием и номером строки
- PASS / FAIL итог

Использование: python scripts/validate.py data/train.jsonl
```

## Задача 5 — Baseline: 10 ответов без файнтюна

Создай `scripts/baseline.py`:

1. Возьми первые 10 примеров из `data/eval.jsonl`
2. Для каждого: извлеки `user` content (текст вакансии)
3. Прогони через gpt-4o-mini БЕЗ системного промпта файнтюна — только:
   ```
   system: "Extract job vacancy information into JSON with fields: title, stack, level, salary_from, currency, remote, location, experience_years_min, experience_years_required"
   user: <текст вакансии>
   ```
4. Сохрани результаты в `data/baseline_results.jsonl`:
   ```json
   {
     "vacancy_text": "...",
     "expected": {...},
     "baseline_response": "...",
     "notes": ""
   }
   ```
5. Выведи в консоль сравнение expected vs baseline для каждого примера

### Критерии оценки (зафиксируй в `data/baseline_criteria.md`)

```markdown
# Критерии оценки качества extraction

## Поля и метрики

| Поле | Метрика | Вес |
|------|---------|-----|
| title | exact/partial match | низкий |
| stack | F1 по элементам массива | высокий |
| level | exact match (enum) | высокий |
| salary_from | exact match или null | средний |
| currency | exact match | средний |
| remote | exact match (enum) | высокий |
| experience_years_min | exact match или null | средний |
| experience_years_required | exact match | средний |

## Что считается "стало лучше"

1. **Format compliance** — модель возвращает валидный JSON с правильными enum-значениями (baseline часто пишет "senior+" или "5+ years" вместо числа)
2. **Stack precision** — не включает мягкие навыки ("коммуникация") в массив stack
3. **Inflated detection** — правильно определяет experience_years_required: inflated для завышенных требований
4. **Null handling** — корректно пишет null когда данных нет, а не придумывает

## Baseline известные слабости (ожидаем увидеть)

- Непоследовательный формат remote ("remote" vs "true" vs "полностью удалённо")
- salary_from как строка "350 000" вместо числа 350000
- stack включает общие слова ("REST API" целиком вместо "REST")
- level "senior+" — не из допустимого enum
```

## Задача 6 — Fine-tune клиент

Создай `scripts/finetune_client.py`:

```python
"""
Fine-tune клиент для OpenAI API.
Этапы: upload file → create job → poll status

НЕ ЗАПУСКАТЬ автоматически. Только подготовить код.
"""
```

Реализуй класс `FineTuneClient` с методами:

```python
class FineTuneClient:
    def upload_file(self, filepath: str) -> str:
        """Загружает JSONL файл, возвращает file_id"""
        
    def create_job(self, file_id: str, model: str = "gpt-4o-mini-2024-07-18", suffix: str = "vacancy-extraction") -> str:
        """Создаёт fine-tune job, возвращает job_id"""
        
    def poll_status(self, job_id: str, interval_seconds: int = 30) -> dict:
        """Поллит статус каждые N секунд до завершения или ошибки"""
        
    def run_full_pipeline(self, train_file: str) -> None:
        """upload → create → poll — полный цикл с логированием"""
```

Добавь CLI:
```bash
python scripts/finetune_client.py --file data/train.jsonl --dry-run  # показать что будет делать
python scripts/finetune_client.py --file data/train.jsonl            # реальный запуск
```

## Структура проекта на выходе

```
day6/
├── data/
│   ├── real_examples.jsonl
│   ├── synthetic_examples.jsonl
│   ├── all_examples.jsonl
│   ├── train.jsonl
│   ├── eval.jsonl
│   ├── baseline_results.jsonl
│   └── baseline_criteria.md
├── scripts/
│   ├── validate.py
│   ├── baseline.py
│   └── finetune_client.py
├── vacancies.txt
└── README.md
```

## Технические требования

- Python 3.12
- `openai>=1.0.0`, `python-dotenv`
- API ключ из `.env` файла: `OPENAI_API_KEY=...`
- Все скрипты запускаются из корня проекта
- Логирование через `logging`, не `print` (кроме итоговой статистики)
- Обработка ошибок API: retry с экспоненциальным backoff (3 попытки)

## Порядок выполнения

1. Установи зависимости
2. Парсинг реальных вакансий → `real_examples.jsonl`
3. Генерация синтетики → `synthetic_examples.jsonl`  
4. Объединение и сплит → `train.jsonl`, `eval.jsonl`
5. Валидация обоих файлов через `validate.py`
6. Baseline → `baseline_results.jsonl`
7. Покажи итоговую статистику: N реальных, N синтетических, N train, N eval, N baseline errors