# День 7 — Оценка уверенности и контроль качества инференса

## Контекст

Продолжаем пайплайн из дня 6: extraction структурированных данных из вакансий.
Задача дня — добавить поверх extraction явную оценку уверенности результата.

Все скрипты размещаем в `finetuning/scripts/`, рядом с кодом дня 6.

## Архитектура

```
Текст вакансии
      │
      ▼
┌─────────────────────┐
│  Extraction         │  gpt-4o-mini → сырой JSON
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Constraint Check   │  без API, мгновенно
│  (всегда первый)    │  → FAIL если формат сломан
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│  Confidence Scoring │  модель оценивает свою уверенность
│                     │  → OK / UNSURE / FAIL + score 0.0-1.0
└─────────────────────┘
      │
      ├── OK     → возвращаем результат
      ├── UNSURE → Self-check (второй вызов модели)
      └── FAIL   → отклоняем
```

## Реализуй 3 подхода

### Подход 1 — Constraint-based (обязательный, без API)

Файл: `finetuning/scripts/confidence/constraint_checker.py`

```python
class ConstraintChecker:
    """
    Проверяет результат extraction без вызова API.
    Запускается всегда первым — бесплатно и мгновенно.
    """

    def check(self, extraction: dict) -> ConstraintResult:
        """
        Возвращает ConstraintResult с полями:
        - status: "OK" | "FAIL"
        - violations: list[str]  # список нарушений
        - warnings: list[str]    # не фатальные проблемы
        """
```

Проверки (violations → FAIL):
- `level` не из enum `{junior, middle, senior, lead, unknown}`
- `remote` не строка из enum `{true, false, hybrid, unknown}`
- `salary_from` не число и не null
- `currency` указан но `salary_from` is null — логическое противоречие
- `stack` не массив или содержит пустые строки
- `experience_years_min` отрицательное или > 30

Проверки (warnings → не FAIL):
- `stack` пустой массив
- `location` is null при `remote == "false"` — подозрительно
- `title` короче 3 символов
- `experience_years_required` == "unknown"

---

### Подход 2 — Confidence Scoring (модель оценивает себя)

Файл: `finetuning/scripts/confidence/confidence_scorer.py`

Модель получает текст вакансии + своё же извлечение и отвечает на вопрос: насколько она уверена?

Системный промпт:
```
You are a quality control assistant for job vacancy data extraction.
You will receive: original vacancy text and extracted JSON.
Your task: evaluate confidence in the extraction quality.

Return ONLY valid JSON:
{
  "status": "OK" | "UNSURE" | "FAIL",
  "score": 0.0-1.0,
  "uncertain_fields": ["field1", "field2"],
  "reason": "brief explanation in English"
}

Scoring rules:
- OK (score >= 0.85): all critical fields extracted clearly, format correct
- UNSURE (score 0.5-0.84): 1-2 fields ambiguous, salary unclear, level inferred
- FAIL (score < 0.5): critical fields missing, text is not a job vacancy, extraction unreliable
```

```python
class ConfidenceScorer:
    def score(self, vacancy_text: str, extraction: dict) -> ScoringResult:
        """
        Возвращает ScoringResult с полями:
        - status: "OK" | "UNSURE" | "FAIL"
        - score: float (0.0 - 1.0)
        - uncertain_fields: list[str]
        - reason: str
        """
```

---

### Подход 3 — Self-check (перепроверка при UNSURE)

Файл: `finetuning/scripts/confidence/self_checker.py`

Запускается только если `ConfidenceScorer` вернул `UNSURE`.
Делает второй независимый extraction и сравнивает с первым.

```python
class SelfChecker:
    def check(self, vacancy_text: str, first_extraction: dict) -> SelfCheckResult:
        """
        1. Делает второй extraction той же вакансии (temperature=0.3 для разнообразия)
        2. Сравнивает поля с first_extraction
        3. Возвращает SelfCheckResult:
           - agreed_fields: list[str]    # поля где оба extraction совпали
           - disagreed_fields: list[str] # поля где есть расхождение
           - final_status: "OK" | "FAIL"
           - merged_extraction: dict     # итоговый extraction (первый при совпадении)
        """
```

Логика финального решения:
- Совпадают >= 75% критических полей (`level`, `remote`, `salary_from`, `stack`) → `OK`, берём первый extraction
- Иначе → `FAIL`, возвращаем ошибку

---

## Главный пайплайн

Файл: `finetuning/scripts/inference_pipeline.py`

```python
class InferencePipeline:
    """
    Полный пайплайн: extraction + confidence control.

    Метрики (накапливаются за сессию):
    - total: int
    - ok_count: int
    - unsure_count: int
    - fail_count: int
    - self_check_triggered: int
    - self_check_rescued: int   # UNSURE → OK после self-check
    - total_api_calls: int
    - total_latency_ms: float
    """

    def process(self, vacancy_text: str) -> PipelineResult:
        """
        Возвращает PipelineResult:
        - extraction: dict | None
        - final_status: "OK" | "UNSURE" | "FAIL"
        - confidence_score: float
        - constraint_violations: list[str]
        - constraint_warnings: list[str]
        - uncertain_fields: list[str]
        - self_check_triggered: bool
        - api_calls_made: int
        - latency_ms: float
        - reason: str
        """

    def get_metrics(self) -> dict:
        """Возвращает накопленную статистику."""

    def print_metrics(self) -> None:
        """Печатает таблицу метрик в консоль."""
```

Порядок в `process()`:
1. Extraction (1 API call)
2. ConstraintChecker → если FAIL: стоп
3. ConfidenceScorer (1 API call)
4. Если OK → возвращаем
5. Если UNSURE → SelfChecker (1 API call) → финальное решение
6. Если FAIL → возвращаем ошибку

---

## Тестирование

Файл: `finetuning/scripts/test_inference.py`

Прогони 30 вакансий через полный пайплайн — по 10 на каждый тип:

### Категория 1 — Простые (ожидаем OK)
Возьми первые 10 примеров из `finetuning/data/eval.jsonl` — там реальные чёткие вакансии.

### Категория 2 — Пограничные (ожидаем UNSURE)
```python
EDGE_CASES = [
    "Ищем крутого разраба. Зарплата: обсуждается. Опыт: желателен.",
    "Senior/Lead Python developer needed. Remote possible. Salary DOE.",
    "Fullstack developer (PHP или Python или JS — на твоё усмотрение).",
    "Стажёр-разработчик. Опыт от 3 лет. Зарплата от 0 до рыночной.",
    "Backend engineer, любой уровень, главное горящие глаза.",
    "We need a rockstar ninja developer. Competitive salary. Skills: everything.",
    "Разработчик (возможно junior, возможно senior — посмотрим).",
    "Python/PHP/JS dev, офис или удалёнка, зарплата белая серая.",
    "AI Engineer — опыт с нейросетями приветствуется, не обязателен.",
    "Developer wanted. Stack TBD. Start ASAP.",
]
```

### Категория 3 — Сложные/шумные (ожидаем FAIL)
```python
NOISY_CASES = [
    "Продам гараж. 500 000 руб. Торг уместен. Звонить после 18:00.",
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod.",
    "",
    "a",
    "СРОЧНО!!! Требуется ВСЁ И ВСЕ!!! Зарплата ОГРОМНАЯ!!! Пиши в личку!!!",
    "Куплю волосы дорого. Цвет любой. Длина от 30см.",
    "Meeting notes: discussed Q3 roadmap, decided to postpone feature X.",
    "Ищу репетитора по математике для ребёнка 10 лет.",
    "Сдам квартиру. 2 комнаты. Метро Сокол. 45 000 в месяц.",
    "Error 404: page not found. Please check the URL and try again.",
]
```

Для каждой категории выводи:
```
=== Категория: Простые ===
[1/10] OK     | score=0.92 | calls=2 | 1.2s | -
[2/10] OK     | score=0.88 | calls=2 | 0.9s | -
[3/10] UNSURE | score=0.71 | calls=3 | 2.1s | self-check → OK
...
```

---

## Итоговый отчёт

В конце выведи и сохрани в `docs/day7/day7-report.md`:

```
╔══════════════════════════════════════════════════════════╗
║              INFERENCE QUALITY REPORT — DAY 7            ║
╠══════════════════════════════════════════════════════════╣
║ Total processed:        30                               ║
║ OK:                     N  (XX%)                         ║
║ UNSURE:                 N  (XX%)                         ║
║ FAIL:                   N  (XX%)                         ║
╠══════════════════════════════════════════════════════════╣
║ Self-check triggered:   N                                ║
║ Self-check rescued:     N  (UNSURE→OK)                   ║
╠══════════════════════════════════════════════════════════╣
║ Total API calls:        N                                ║
║ Avg calls per request:  X.X                              ║
║ Avg latency:            X.Xs                             ║
╚══════════════════════════════════════════════════════════╝
```

---

## Структура файлов на выходе

```
finetuning/
└── scripts/
    ├── confidence/
    │   ├── __init__.py
    │   ├── constraint_checker.py
    │   ├── confidence_scorer.py
    │   └── self_checker.py
    ├── inference_pipeline.py
    └── test_inference.py
docs/
└── day7/
    └── day7-report.md
```

---

## Технические требования

- Python 3.12, `openai>=1.0.0`, `python-dotenv`
- Все результаты — через `@dataclass` или `TypedDict`
- Логирование через `logging`, не `print` (кроме итогового отчёта)
- `temperature=0` для extraction и scoring, `temperature=0.3` для self-check
- API ключ из `.env`: `OPENAI_API_KEY=...`
- Retry с backoff — переиспользуй подход из `parse_vacancies.py`

## Порядок выполнения

1. Создай структуру папок `finetuning/scripts/confidence/`
2. Реализуй `ConstraintChecker` — без API, можно сразу проверить вручную
3. Реализуй `ConfidenceScorer`
4. Реализуй `SelfChecker`
5. Собери `InferencePipeline`
6. Запусти `test_inference.py` на 30 вакансиях
7. Сохрани отчёт в `docs/day7/day7-report.md`