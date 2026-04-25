# День 9 — Декомпозиция инференса (multi-stage inference)

## Контекст

Продолжаем пайплайн. Сегодня сравниваем два подхода к extraction:
- **Monolithic**: один большой промпт, один вызов, все поля сразу
- **Multi-stage**: три коротких специализированных вызова

Задача — реализовать оба, прогнать на одних данных, сравнить качество и стоимость.

**Важно:** существующий `InferencePipeline` из дня 7 — это уже monolithic подход.
Сегодня реализуем multi-stage как альтернативу и честно сравниваем.

## Архитектура multi-stage

```
Текст вакансии
      │
      ▼
┌─────────────────────────────────┐
│  Stage 1 — Classification       │  gpt-4o-mini
│  Вход: сырой текст              │  ~50 токенов ответа
│  Выход: is_vacancy, language,   │
│         structure_quality       │
└─────────────────────────────────┘
      │
      ├── is_vacancy=false → SKIP (не тратим Stage 2-3)
      │
      ▼
┌─────────────────────────────────┐
│  Stage 2 — Raw Extraction       │  gpt-4o-mini
│  Вход: текст + язык из Stage 1  │  ~200 токенов ответа
│  Выход: сырые поля без          │
│         нормализации            │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│  Stage 3 — Normalization        │  gpt-4o-mini
│  Вход: сырые поля из Stage 2    │  ~150 токенов ответа
│  Выход: строгий JSON по схеме   │
│         (enum, числа, null)     │
└─────────────────────────────────┘
```

## Задача 1 — Stage 1: Classification

Файл: `finetuning/scripts/multistage/stage1_classifier.py`

Системный промпт Stage 1:
```
You are a text classifier. Analyze the input text and determine if it is a job vacancy.
Return ONLY valid JSON, no explanation.
```

User промпт:
```
Classify this text:

{text}

Return JSON:
{
  "is_vacancy": true | false,
  "language": "ru" | "en" | "mixed",
  "structure_quality": "high" | "medium" | "low",
  "reason": "one sentence"
}

structure_quality:
- high: clear sections, explicit salary, level, stack
- medium: some fields implicit or missing
- low: very short, chaotic, or ambiguous text
```

```python
@dataclass
class Stage1Result:
    is_vacancy: bool
    language: str       # ru | en | mixed
    structure_quality: str  # high | medium | low
    reason: str
    tokens_used: int
    latency_ms: float


class Stage1Classifier:
    def classify(self, text: str) -> Stage1Result:
        ...
```

`temperature=0`, `max_tokens=100`

## Задача 2 — Stage 2: Raw Extraction

Файл: `finetuning/scripts/multistage/stage2_extractor.py`

Принимает текст + результат Stage 1 (язык и structure_quality).
Извлекает поля как есть — без нормализации к enum.

Системный промпт Stage 2:
```
You are a data extraction assistant. Extract job vacancy fields exactly as written in the text.
Do not normalize or interpret — extract raw values only.
Return ONLY valid JSON.
```

User промпт:
```
Text language: {language}
Structure quality: {structure_quality}

Extract from this vacancy text:

{text}

Return JSON with raw extracted values:
{
  "title_raw": "as written",
  "stack_raw": ["as written"],
  "level_raw": "as written or null",
  "salary_raw": "as written or null",
  "remote_raw": "as written or null",
  "location_raw": "as written or null",
  "experience_raw": "as written or null"
}
```

```python
@dataclass
class Stage2Result:
    title_raw: str
    stack_raw: list[str]
    level_raw: str | None
    salary_raw: str | None
    remote_raw: str | None
    location_raw: str | None
    experience_raw: str | None
    tokens_used: int
    latency_ms: float


class Stage2Extractor:
    def extract(self, text: str, stage1: Stage1Result) -> Stage2Result:
        ...
```

`temperature=0`, `max_tokens=300`

## Задача 3 — Stage 3: Normalization

Файл: `finetuning/scripts/multistage/stage3_normalizer.py`

Принимает сырые поля из Stage 2, нормализует к строгой схеме.
Это критический этап — именно здесь происходит перевод в enum, числа, null.

Системный промпт Stage 3:
```
You are a data normalization assistant. Convert raw job vacancy fields to a strict schema.
Return ONLY valid JSON with exact types specified.
```

User промпт:
```
Normalize these raw extracted fields to strict schema:

Raw data:
{stage2_json}

Return normalized JSON:
{
  "title": "string",
  "stack": ["array of specific technologies only, no soft skills"],
  "level": "junior" | "middle" | "senior" | "lead" | "unknown",
  "salary_from": number | null,
  "currency": "RUB" | "USD" | "EUR" | null,
  "remote": "true" | "false" | "hybrid" | "unknown",
  "location": "string" | null,
  "experience_years_min": number | null,
  "experience_years_required": "normal" | "inflated" | "unknown"
}

Rules:
- salary_from: extract minimum number only, no strings like "350 000" → 350000
- remote: "true" if fully remote, "false" if office only, "hybrid" if mixed
- stack: exclude "REST API", "Git", "Agile", "коммуникация" and similar non-tech items
- experience_years_required: "inflated" if years > 4 for roles where 2-3 years suffice with AI tools
```

```python
@dataclass
class Stage3Result:
    extraction: dict   # финальный нормализованный JSON по схеме
    tokens_used: int
    latency_ms: float


class Stage3Normalizer:
    def normalize(self, stage2: Stage2Result) -> Stage3Result:
        ...
```

`temperature=0`, `max_tokens=250`

## Задача 4 — MultiStagePipeline

Файл: `finetuning/scripts/multistage/pipeline.py`

```python
@dataclass
class MultiStageResult:
    extraction: dict | None
    final_status: str           # OK | SKIP | FAIL
    skip_reason: str            # если SKIP — почему (not_vacancy)
    stage1: Stage1Result | None
    stage2: Stage2Result | None
    stage3: Stage3Result | None
    total_tokens: int
    total_api_calls: int
    latency_ms: float


class MultiStagePipeline:
    """
    Метрики:
    - total: int
    - ok_count: int
    - skip_count: int   # не вакансия, пропущено на Stage 1
    - fail_count: int
    - total_tokens: int
    - total_api_calls: int
    - total_latency_ms: float
    """

    def process(self, text: str) -> MultiStageResult:
        """
        1. Stage 1 → если not vacancy: SKIP
        2. Stage 2 → raw extraction
        3. Stage 3 → normalization
        4. ConstraintChecker → если violations: FAIL
        5. OK
        """

    def print_metrics(self) -> None:
        ...
```

Используй `ConstraintChecker` из дня 7 после Stage 3 — он уже умеет проверять финальный JSON.

## Задача 5 — Сравнительное тестирование

Файл: `finetuning/scripts/multistage/test_multistage.py`

Прогони **те же 30 вакансий** что в днях 7-8 через оба пайплайна и сравни.

Для каждой вакансии запускай последовательно:
1. `InferencePipeline.process()` — monolithic (день 7)
2. `MultiStagePipeline.process()` — multi-stage (день 9)

Вывод per-item:
```
=== Категория: Простые ===
[ 1/10] Monolithic: OK   score=0.91 calls=2 1.1s | Multi-stage: OK   calls=3 1.8s tokens=412
[ 2/10] Monolithic: FAIL calls=2 0.8s          | Multi-stage: SKIP  calls=1 0.3s (not_vacancy)
```

## Задача 6 — Сравнительный отчёт

Сохрани в `docs/day9/day9-report.md`:

```
╔══════════════════════════════════════════════════════════════════════╗
║                    COMPARISON REPORT — DAY 9                         ║
╠══════════════════════════════════════════════════════════════════════╣
║                        MONOLITHIC (Day 7)                            ║
║  OK:           N  (XX%)                                              ║
║  FAIL:         N  (XX%)                                              ║
║  API calls:    N total | X.X avg per request                         ║
║  Avg latency:  X.Xs                                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                        MULTI-STAGE (Day 9)                           ║
║  OK:           N  (XX%)                                              ║
║  SKIP:         N  (XX%) — filtered at Stage 1 (not vacancy)          ║
║  FAIL:         N  (XX%)                                              ║
║  API calls:    N total | X.X avg per request                         ║
║  Avg latency:  X.Xs                                                  ║
║  Total tokens: N | X avg per request                                 ║
╠══════════════════════════════════════════════════════════════════════╣
║                        DELTA                                         ║
║  Calls saved by Stage 1 filter:  N                                   ║
║  Latency overhead (multi vs mono): +X.Xs avg                         ║
║  Constraint violations:                                              ║
║    Monolithic:   N violations                                        ║
║    Multi-stage:  N violations                                        ║
╚══════════════════════════════════════════════════════════════════════╝
```

## Структура файлов

```
finetuning/
└── scripts/
    └── multistage/
        ├── __init__.py
        ├── stage1_classifier.py
        ├── stage2_extractor.py
        ├── stage3_normalizer.py
        ├── pipeline.py
        └── test_multistage.py
docs/
└── day9/
    └── day9-report.md
```

## Технические требования

- Python 3.12, `openai>=1.0.0`, `python-dotenv`
- Все результаты через `@dataclass`
- Retry логику берём из `utils/openai_utils.py` (день 8)
- `temperature=0` для всех стадий
- API ключ из `.env`

## Порядок выполнения

1. Создай структуру `multistage/`
2. Stage 1 → протестируй вручную на 2-3 примерах
3. Stage 2, Stage 3
4. `MultiStagePipeline` — собери и проверь на одном примере
5. `test_multistage.py` — 30 вакансий, оба пайплайна
6. Сохрани отчёт