# День 10 — Micro-model first: проверка перед LLM

## Контекст

Продолжаем пайплайн. Сегодня добавляем нулевой уровень перед любыми cloud API вызовами.

Идея: Stage 1 из дня 9 делает классификацию через gpt-4o-mini — это стоит денег и ~0.5-1с.
Можно заменить его локальной крошечной моделью через Ollama — бесплатно и ~100мс.

**Micro-model задача**: определить, является ли текст вакансией (is_vacancy),
и если да — какого качества структура (structure_quality: high/medium/low).
Это ровно то, что делал Stage 1 — просто теперь локально.

**Важно:** Ollama уже установлен с первой недели курса.
Используем **две модели для сравнения**:
- Primary: `qwen2.5:0.5b` (397MB — настоящая micro-model, цель: максимальная скорость)
- Fallback: `qwen2.5:3b` (1.9GB — если accuracy 0.5b окажется < 70%)

## Архитектура

```
Текст вакансии
      │
      ▼
┌─────────────────────────────────┐
│  Micro-model (Ollama, локально) │  бесплатно, ~50-200мс
│  qwen2.5:0.5b (primary)        │
│  Выход: is_vacancy, quality,    │
│         confidence: OK/UNSURE   │
└─────────────────────────────────┘
      │
      ├── is_vacancy=false + confidence=OK → REJECT (0 cloud вызовов)
      │
      ├── confidence=UNSURE → Stage 1 cloud (gpt-4o-mini уточняет)
      │
      └── is_vacancy=true + confidence=OK
                  │
                  ▼
      ┌─────────────────────────────────┐
      │  Stage 2 + Stage 3 (cloud)      │  как в день 9
      │  Raw extraction + Normalize     │
      └─────────────────────────────────┘
```

## Задача 1 — MicroClassifier (Ollama)

Файл: `finetuning/scripts/micro/micro_classifier.py`

```python
@dataclass
class MicroResult:
    is_vacancy: bool
    structure_quality: str   # high | medium | low
    confidence: str          # OK | UNSURE
    reason: str
    latency_ms: float
    model: str               # какая модель использовалась


class MicroClassifier:
    """
    Локальный классификатор через Ollama HTTP API.
    Не использует openai SDK — прямые запросы к http://localhost:11434.
    """

    def __init__(self, model: str = "qwen2.5:0.5b") -> None:
        self.model = model
        self.base_url = "http://localhost:11434"

    def classify(self, text: str) -> MicroResult:
        """
        Возвращает MicroResult.
        confidence=UNSURE если модель не уверена (пограничный случай).
        """

    def is_available(self) -> bool:
        """Проверяет что Ollama запущена и модель доступна."""
```

Промпт для micro-model (должен быть коротким — маленькая модель):
```
You are a text classifier. Determine if the text is a job vacancy posting.

Text:
{text}

Reply with JSON only:
{
  "is_vacancy": true or false,
  "structure_quality": "high" or "medium" or "low",
  "confidence": "OK" or "UNSURE",
  "reason": "one short sentence"
}

confidence=UNSURE if: text is borderline, very short, or you are not certain.
```

Используй Ollama `/api/generate` endpoint с `"stream": false`.
`temperature=0.1` (не 0 — маленькие модели хуже работают с temperature=0).
Timeout: 10 секунд.

## Задача 2 — MicroFirstPipeline

Файл: `finetuning/scripts/micro/pipeline.py`

```python
@dataclass
class MicroFirstResult:
    extraction: dict | None
    final_status: str          # OK | SKIP | UNSURE_ESCALATED | FAIL
    micro_result: MicroResult
    used_cloud_stage1: bool    # было ли облачное уточнение Stage 1
    cloud_stage1_result: Stage1Result | None
    stage2: Stage2Result | None
    stage3: Stage3Result | None
    total_cloud_calls: int     # только cloud вызовы (без micro)
    total_latency_ms: float
    micro_latency_ms: float    # latency micro-model отдельно
    cloud_latency_ms: float    # latency cloud вызовов отдельно


class MicroFirstPipeline:
    """
    Метрики:
    - total: int
    - micro_rejected: int      # SKIP без cloud вызовов
    - micro_unsure: int        # эскалировано на cloud Stage 1
    - micro_passed: int        # прошло напрямую к Stage 2-3
    - ok_count: int
    - fail_count: int
    - total_cloud_calls: int
    - total_micro_latency_ms: float
    - total_cloud_latency_ms: float
    """

    def __init__(self, openai_client, micro_model: str = "qwen2.5:0.5b") -> None:
        self.micro = MicroClassifier(micro_model)
        # Stage2Extractor, Stage3Normalizer, Stage1Classifier (для UNSURE fallback)
        ...

    def process(self, text: str) -> MicroFirstResult:
        """
        1. MicroClassifier.classify()
        2. Если micro: is_vacancy=False + confidence=OK → SKIP (0 cloud calls)
        3. Если micro: confidence=UNSURE → Stage1Classifier (cloud) для уточнения
           → если cloud говорит not_vacancy → SKIP
           → если cloud говорит vacancy → продолжаем
        4. Если micro: is_vacancy=True + confidence=OK → сразу Stage 2-3
        5. Stage 2 + Stage 3 + ConstraintChecker
        """

    def print_metrics(self) -> None:
        """
        Выводит таблицу с разбивкой:
        - сколько запросов отсёк micro без cloud
        - сколько cloud вызовов сэкономлено
        - latency micro vs cloud отдельно
        """
```

## Задача 3 — Fallback при недоступности Ollama

В `MicroFirstPipeline.process()` добавь обработку:

```python
if not self.micro.is_available():
    logger.warning("Ollama unavailable, falling back to MultiStagePipeline")
    # fallback на day9 pipeline без micro
    ...
```

Это важно — пайплайн не должен падать если Ollama не запущена.

## Задача 4 — Тестирование

Файл: `finetuning/scripts/micro/test_micro.py`

Прогони те же 30 вакансий (3 категории × 10) через четыре пайплайна:

1. `MultiStagePipeline` (день 9) — baseline
2. `MicroFirstPipeline(model="qwen2.5:0.5b")` — primary micro
3. `MicroFirstPipeline(model="qwen2.5:3b")` — fallback micro для сравнения
4. `MicroClassifier` отдельно — точность обеих моделей как классификаторов

### Секция A — точность micro-models как классификаторов

Прогони оба `MicroClassifier` на всех 30 вакансиях и сравни:

```
[ 1/30] 0.5b: is_vacancy=True  conf=OK    | 3b: is_vacancy=True  conf=OK  | Expected: True  | ✓✓
[ 2/30] 0.5b: is_vacancy=False conf=OK    | 3b: is_vacancy=False conf=OK  | Expected: False | ✓✓
[ 3/30] 0.5b: is_vacancy=True  conf=UNSURE| 3b: is_vacancy=False conf=OK  | Expected: False | ✗✓
```

Посчитай для каждой модели:
- Accuracy на is_vacancy (N/30)
- % UNSURE случаев
- Avg latency
- Сколько ошибок исправил cloud Stage 1 при UNSURE

### Секция B — сравнение пайплайнов

```
=== Категория: Простые ===
[ 1/10] Day9: OK calls=3 1.8s | 0.5b: OK cloud=2 micro=80ms  | 3b: OK cloud=2 micro=180ms
[ 2/10] Day9: OK calls=3 2.1s | 0.5b: OK cloud=2 micro=90ms  | 3b: OK cloud=2 micro=210ms
```

## Задача 5 — Итоговый отчёт

Сохрани в `docs/day10/day10-report.md`:

```
╔══════════════════════════════════════════════════════════════════════╗
║                    MICRO-MODEL REPORT — DAY 10                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  MICRO-MODEL ACCURACY (30 requests)                                  ║
║                        qwen2.5:0.5b    qwen2.5:3b                   ║
║  Correct (vacancy/not): N/30 (XX%)     N/30 (XX%)                   ║
║  UNSURE cases:          N    (XX%)     N    (XX%)                   ║
║  Avg latency:           XXms           XXms                          ║
║  UNSURE→cloud fixed:    N              N                             ║
╠══════════════════════════════════════════════════════════════════════╣
║  PIPELINE COMPARISON (30 requests)                                   ║
║                     Day 9    0.5b-first  3b-first                   ║
║  OK:                N(XX%)   N(XX%)      N(XX%)                     ║
║  SKIP/REJECT:       N(XX%)   N(XX%)      N(XX%)                     ║
║  Cloud calls total: N        N           N                           ║
║  Avg cloud calls:   X.X      X.X         X.X                        ║
║  Avg total latency: X.Xs     X.Xs        X.Xs                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  SAVINGS vs Day 9 (best micro model)                                 ║
║  Cloud calls saved: N  (XX% reduction)                              ║
║  Micro latency add: +XXXms avg                                      ║
║  Net latency delta: +/-X.Xs avg                                     ║
╚══════════════════════════════════════════════════════════════════════╝
```

## Структура файлов

```
finetuning/
└── scripts/
    └── micro/
        ├── __init__.py
        ├── micro_classifier.py
        ├── pipeline.py
        └── test_micro.py
docs/
└── day10/
    └── day10-report.md
```

## Технические требования

- Python 3.12, `requests` (для Ollama HTTP), `openai>=1.0.0`, `python-dotenv`
- Ollama: `http://localhost:11434/api/generate`
- Timeout Ollama запросов: 10 секунд
- Retry для Ollama: 2 попытки (не 3 — локальный сервис)
- Retry для cloud: `utils/openai_utils.py`
- Логировать latency micro и cloud отдельно

## Порядок выполнения

1. Проверь доступные модели: `ollama list` — убедись что есть `qwen2.5:0.5b` и `qwen2.5:3b`
2. Реализуй `MicroClassifier` с параметром `model`
3. Протестируй вручную: `MicroClassifier("qwen2.5:0.5b")` и `MicroClassifier("qwen2.5:3b")` на 3 примерах
4. Реализуй `MicroFirstPipeline` с fallback на MultiStagePipeline
5. `test_micro.py` — 30 вакансий, все четыре варианта
6. Сохрани отчёт