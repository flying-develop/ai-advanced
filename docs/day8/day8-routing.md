# День 8 — Routing между моделями

## Контекст

Продолжаем пайплайн дней 6–7. Сегодня заменяем Self-check на routing:
вместо того чтобы прогонять ту же модель повторно при UNSURE —
эскалируем на более сильную модель.

**Важно:** `SelfChecker` из дня 7 не удаляем — он остаётся как fallback.
Routing — это новый слой поверх существующего пайплайна.

## Архитектура

```
Текст вакансии
      │
      ▼
┌──────────────────────────┐
│  Router                  │
│  выбирает стартовую      │
│  модель по эвристикам    │
└──────────────────────────┘
      │
      ▼
┌──────────────────────────┐
│  Tier 1: gpt-4o-mini     │  быстро, дёшево
│  extraction + confidence │
└──────────────────────────┘
      │
      ├── OK   ──────────────────────→ результат
      │
      ├── UNSURE ──→ ┌──────────────────────────┐
      │              │  Tier 2: gpt-4o          │  медленно, дорого
      │              │  повторный extraction    │
      │              └──────────────────────────┘
      │                      │
      │                      ├── OK   → результат
      │                      └── FAIL → отклонить
      │
      └── FAIL ─────────────────────→ отклонить
```

## Задача 1 — ModelRouter

Файл: `finetuning/scripts/routing/model_router.py`

```python
class ModelRouter:
    """
    Определяет стартовую модель и пороги эскалации.

    Эвристики выбора стартовой модели:
    1. Длина текста: если < 100 символов → сразу gpt-4o (слишком мало данных для mini)
    2. Язык: определяем по первым 200 символам — если смешанный → gpt-4o
    3. Default: gpt-4o-mini

    Порог эскалации:
    - confidence score < 0.75 → эскалировать на gpt-4o
    - статус UNSURE → эскалировать
    - статус FAIL → не эскалировать, отклонить
    """

    TIER1_MODEL = "gpt-4o-mini"
    TIER2_MODEL = "gpt-4o"
    ESCALATION_THRESHOLD = 0.75

    def select_initial_model(self, vacancy_text: str) -> str:
        """
        Возвращает название модели для первого запроса.
        Логирует причину выбора.
        """

    def should_escalate(self, result: PipelineResult) -> bool:
        """
        True если нужно эскалировать на Tier 2.
        """

    def get_escalation_reason(self, result: PipelineResult) -> str:
        """
        Человекочитаемая причина эскалации для логов и отчёта.
        """
```

## Задача 2 — RoutedPipeline

Файл: `finetuning/scripts/routing/routed_pipeline.py`

Расширяет `InferencePipeline` из дня 7, добавляя routing.

```python
@dataclass
class RoutedResult:
    extraction: dict | None
    final_status: str           # OK | FAIL
    confidence_score: float
    initial_model: str          # какая модель обработала первой
    escalated: bool             # была ли эскалация
    escalation_reason: str      # почему эскалировали (или "")
    tier1_calls: int            # вызовы gpt-4o-mini
    tier2_calls: int            # вызовы gpt-4o
    total_calls: int
    latency_ms: float
    constraint_violations: list[str]
    constraint_warnings: list[str]


class RoutedPipeline:
    """
    Метрики (накапливаются за сессию):
    - total: int
    - ok_count: int
    - fail_count: int
    - tier1_only: int       # обработано только gpt-4o-mini
    - escalated_count: int  # ушло на gpt-4o
    - escalated_ok: int     # после эскалации стало OK
    - escalated_fail: int   # после эскалации всё равно FAIL
    - total_tier1_calls: int
    - total_tier2_calls: int
    - total_latency_ms: float
    """

    def __init__(self, openai_client):
        self.router = ModelRouter()
        self.constraint_checker = ConstraintChecker()
        self.confidence_scorer = ConfidenceScorer(openai_client)
        # метрики...

    def process(self, vacancy_text: str) -> RoutedResult:
        """
        Полный цикл с routing:
        1. Router выбирает стартовую модель
        2. Extraction на стартовой модели
        3. ConstraintChecker
        4. ConfidenceScorer
        5. Если should_escalate → повторный extraction на gpt-4o
        6. Финальный ConstraintChecker на результате Tier 2
        """

    def print_metrics(self) -> None:
        """Печатает итоговую таблицу."""
```

## Задача 3 — Утилита (рефакторинг)

Файл: `finetuning/scripts/utils/openai_utils.py`

`_extract_with_retry` продублирован в `parse_vacancies.py` и `inference_pipeline.py`.
Вынеси в общую утилиту:

```python
def call_with_retry(
    client,
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0,
    max_tokens: int = 512,
    max_retries: int = 3,
) -> str:
    """OpenAI chat completion с экспоненциальным backoff."""
```

Обнови `inference_pipeline.py` и `parse_vacancies.py` — импортируй из утилиты
вместо дублированного кода.

## Задача 4 — Тест routing

Файл: `finetuning/scripts/routing/test_routing.py`

Прогони 30 вакансий — те же категории что в день 7, чтобы можно было сравнить:

```python
SIMPLE_CASES   = [взять из eval.jsonl первые 10]
EDGE_CASES     = [те же 10 из дня 7]
NOISY_CASES    = [те же 10 из дня 7]
```

Для каждого запроса выводи:

```
=== Категория: Простые ===
[ 1/10] OK   | mini→OK   | score=0.91 | calls=2 (2+0) | 1.1s
[ 2/10] OK   | mini→gpt4 | score=0.95 | calls=4 (2+2) | 3.2s | escalated: UNSURE score=0.71
[ 3/10] FAIL | mini→FAIL | score=0.31 | calls=2 (2+0) | 0.9s
```

Формат строки:
```
[N/10] STATUS | ROUTE | score=X.XX | calls=N (tier1+tier2) | Xs | [причина эскалации]
```

Где ROUTE:
- `mini→OK` — обработано gpt-4o-mini, результат OK
- `mini→gpt4` — эскалировано на gpt-4o
- `gpt4→OK` — роутер сразу выбрал gpt-4o (короткий текст / смешанный язык)
- `mini→FAIL` — gpt-4o-mini не справился, не эскалировали

## Задача 5 — Сравнительный отчёт

В конце `test_routing.py` выведи и сохрани в `docs/day8/day8-report.md`:

```
╔══════════════════════════════════════════════════════════════╗
║              ROUTING REPORT — DAY 8                          ║
╠══════════════════════════════════════════════════════════════╣
║ Total processed:          30                                 ║
║ OK:                       N  (XX%)                          ║
║ FAIL:                     N  (XX%)                          ║
╠══════════════════════════════════════════════════════════════╣
║ Stayed on gpt-4o-mini:    N  (XX%) — tier1 only             ║
║ Escalated to gpt-4o:      N  (XX%)                          ║
║   └─ rescued after esc.:  N  (XX% of escalated)             ║
║   └─ failed after esc.:   N                                 ║
╠══════════════════════════════════════════════════════════════╣
║ Total API calls:          N                                  ║
║   Tier 1 (mini) calls:    N                                  ║
║   Tier 2 (gpt-4o) calls:  N                                  ║
║ Avg calls per request:    X.X                                ║
║ Avg latency:              X.Xs                               ║
╠══════════════════════════════════════════════════════════════╣
║ vs Day 7 self-check:                                         ║
║   Day 7 total calls:      [вставь вручную из day7-report]   ║
║   Day 8 total calls:      N                                  ║
║   Разница:                +N / -N                            ║
╚══════════════════════════════════════════════════════════════╝
```

Последний блок сравнения с днём 7 заполни вручную после запуска — это для видео.

## Структура файлов

```
finetuning/
└── scripts/
    ├── routing/
    │   ├── __init__.py
    │   ├── model_router.py
    │   ├── routed_pipeline.py
    │   └── test_routing.py
    └── utils/
        ├── __init__.py
        └── openai_utils.py
docs/
└── day8/
    └── day8-report.md
```

## Технические требования

- Python 3.12, `openai>=1.0.0`, `python-dotenv`
- Все результаты через `@dataclass`
- `temperature=0` для обоих tier
- Retry логику берём из `utils/openai_utils.py` (новая утилита)
- API ключ из `.env`

## Порядок выполнения

1. Создай `utils/openai_utils.py`, перенеси retry-логику
2. Обнови `inference_pipeline.py` и `parse_vacancies.py` — используй утилиту
3. Реализуй `ModelRouter`
4. Реализуй `RoutedPipeline`
5. Запусти `test_routing.py`
6. Заполни блок сравнения в `day8-report.md` вручную