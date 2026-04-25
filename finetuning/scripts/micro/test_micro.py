"""Compare MicroFirstPipeline vs MultiStagePipeline on 30 vacancies across 3 categories."""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_scripts = Path(__file__).parent.parent
_multistage = _scripts / "multistage"
_micro = Path(__file__).parent
for _p in [str(_scripts), str(_multistage)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
# Force _micro first — Python auto-adds script dir to sys.path[0], but
# multistage/pipeline.py would shadow micro/pipeline.py after _multistage insert.
if str(_micro) in sys.path:
    sys.path.remove(str(_micro))
sys.path.insert(0, str(_micro))

from micro_classifier import MicroClassifier
from pipeline import MicroFirstPipeline
from multistage.pipeline import MultiStagePipeline

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

EVAL_FILE = Path("finetuning/data/eval.jsonl")
REPORT_PATH = Path("docs/day10/day10-report.md")

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

# Expected is_vacancy for accuracy scoring
EDGE_EXPECTED = [True] * 10   # all edge cases are vacancies (borderline)
NOISY_EXPECTED = [False] * 10  # none of the noisy cases are vacancies


def load_simple_cases() -> list[str]:
    """Load first 10 vacancy texts from eval.jsonl."""
    cases = []
    with EVAL_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            for msg in record.get("messages", []):
                if msg.get("role") == "user":
                    cases.append(msg["content"])
                    break
            if len(cases) >= 10:
                break
    return cases


# ─── Section A: micro accuracy comparison ────────────────────────────────────

def run_classifier_accuracy(
    clf05: MicroClassifier,
    clf3b: MicroClassifier,
    cases: list[str],
    expected: list[bool],
    label: str,
) -> tuple[list, list]:
    """Run both classifiers and print per-item comparison. Returns (res05, res3b)."""
    res05, res3b = [], []
    print(f"\n=== Классификатор: {label} ===")
    for i, (text, exp) in enumerate(zip(cases, expected), 1):
        r05 = clf05.classify(text)
        r3b = clf3b.classify(text)
        res05.append(r05)
        res3b.append(r3b)

        ok05 = "✓" if r05.is_vacancy == exp else "✗"
        ok3b = "✓" if r3b.is_vacancy == exp else "✗"
        print(
            f"[{i:2d}/{len(cases)}] "
            f"0.5b: is_vacancy={str(r05.is_vacancy):<5} conf={r05.confidence:<6} | "
            f"3b: is_vacancy={str(r3b.is_vacancy):<5} conf={r3b.confidence:<6} | "
            f"Expected: {str(exp):<5} | {ok05}{ok3b}"
        )
    return res05, res3b


# ─── Section B: pipeline comparison ──────────────────────────────────────────

def run_pipeline_comparison(
    day9: MultiStagePipeline,
    pipe05: MicroFirstPipeline,
    pipe3b: MicroFirstPipeline,
    label: str,
    cases: list[str],
) -> None:
    """Run all three pipelines and print per-item comparison."""
    print(f"\n=== Категория: {label} ===")
    for i, text in enumerate(cases, 1):
        d9 = day9.process(text)
        m05 = pipe05.process(text)
        m3b = pipe3b.process(text)

        d9_str = f"Day9: {d9.final_status:<4} calls={d9.total_api_calls} {d9.latency_ms/1000:.1f}s"
        m05_str = (
            f"0.5b: {m05.final_status:<16} cloud={m05.total_cloud_calls} "
            f"micro={m05.micro_latency_ms:.0f}ms"
        )
        m3b_str = (
            f"3b: {m3b.final_status:<16} cloud={m3b.total_cloud_calls} "
            f"micro={m3b.micro_latency_ms:.0f}ms"
        )
        print(f"[{i:2d}/{len(cases)}] {d9_str} | {m05_str} | {m3b_str}")


# ─── Report builder ───────────────────────────────────────────────────────────

def build_report(
    day9: MultiStagePipeline,
    pipe05: MicroFirstPipeline,
    pipe3b: MicroFirstPipeline,
    all_res05: list,
    all_res3b: list,
    all_expected: list[bool],
    unsure_fixed_05: int,
    unsure_fixed_3b: int,
) -> str:
    """Build ASCII report."""
    total = len(all_expected)

    acc05 = sum(1 for r, e in zip(all_res05, all_expected) if r.is_vacancy == e)
    acc3b = sum(1 for r, e in zip(all_res3b, all_expected) if r.is_vacancy == e)
    unsure05 = sum(1 for r in all_res05 if r.confidence == "UNSURE")
    unsure3b = sum(1 for r in all_res3b if r.confidence == "UNSURE")
    lat05 = sum(r.latency_ms for r in all_res05) / total
    lat3b = sum(r.latency_ms for r in all_res3b) / total

    d9m = day9.get_metrics()
    m05m = pipe05.get_metrics()
    m3bm = pipe3b.get_metrics()
    pt = d9m["total"] or 1

    d9_ok_pct = d9m["ok_count"] / pt * 100
    d9_skip_pct = d9m["skip_count"] / pt * 100
    m05_ok_pct = m05m["ok_count"] / pt * 100
    m05_skip_pct = (m05m["micro_rejected"] + m05m["micro_unsure"]) / pt * 100
    m3b_ok_pct = m3bm["ok_count"] / pt * 100
    m3b_skip_pct = (m3bm["micro_rejected"] + m3bm["micro_unsure"]) / pt * 100

    best_saved = d9m["total_api_calls"] - min(m05m["total_cloud_calls"], m3bm["total_cloud_calls"])
    best_pct = best_saved / (d9m["total_api_calls"] or 1) * 100

    best_model = "0.5b" if m05m["total_cloud_calls"] <= m3bm["total_cloud_calls"] else "3b"
    best_micro_ms = m05m["avg_micro_latency_ms"] if best_model == "0.5b" else m3bm["avg_micro_latency_ms"]
    d9_avg_lat = d9m["avg_latency_ms"] / 1000
    best_avg_lat = (
        (m05m["avg_micro_latency_ms"] + m05m["avg_cloud_latency_ms"]) / 1000
        if best_model == "0.5b"
        else (m3bm["avg_micro_latency_ms"] + m3bm["avg_cloud_latency_ms"]) / 1000
    )
    lat_delta = best_avg_lat - d9_avg_lat

    lines = [
        "# Micro-Model Report — Day 10\n",
        "```",
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║                    MICRO-MODEL REPORT — DAY 10                       ║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        "║  MICRO-MODEL ACCURACY (30 requests)                                  ║",
        f"║                        qwen2.5:0.5b    qwen2.5:3b                   ║",
        f"║  Correct (vacancy/not): {acc05}/{total} ({acc05/total*100:.0f}%)     {acc3b}/{total} ({acc3b/total*100:.0f}%)                   ║",
        f"║  UNSURE cases:          {unsure05:<4} ({unsure05/total*100:.0f}%)     {unsure3b:<4} ({unsure3b/total*100:.0f}%)                  ║",
        f"║  Avg latency:           {lat05:.0f}ms           {lat3b:.0f}ms                          ║",
        f"║  UNSURE→cloud fixed:    {unsure_fixed_05:<14} {unsure_fixed_3b:<14}              ║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        "║  PIPELINE COMPARISON (30 requests)                                   ║",
        f"║                     Day 9    0.5b-first  3b-first                   ║",
        f"║  OK:                {d9m['ok_count']:>3}({d9_ok_pct:.0f}%)  {m05m['ok_count']:>3}({m05_ok_pct:.0f}%)     {m3bm['ok_count']:>3}({m3b_ok_pct:.0f}%)                ║",
        f"║  SKIP/REJECT:       {d9m['skip_count']:>3}({d9_skip_pct:.0f}%)  {m05m['micro_rejected']:>3}({m05_skip_pct:.0f}%)     {m3bm['micro_rejected']:>3}({m3b_skip_pct:.0f}%)                ║",
        f"║  Cloud calls total: {d9m['total_api_calls']:<6}   {m05m['total_cloud_calls']:<10} {m3bm['total_cloud_calls']:<10}           ║",
        f"║  Avg cloud calls:   {d9m['avg_calls']:.1f}      {m05m['avg_cloud_calls']:.1f}         {m3bm['avg_cloud_calls']:.1f}                   ║",
        f"║  Avg total latency: {d9_avg_lat:.1f}s     {(m05m['avg_micro_latency_ms']+m05m['avg_cloud_latency_ms'])/1000:.1f}s        {(m3bm['avg_micro_latency_ms']+m3bm['avg_cloud_latency_ms'])/1000:.1f}s                  ║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        f"║  SAVINGS vs Day 9 (best micro model: {best_model})                        ║",
        f"║  Cloud calls saved: {best_saved:<2}  ({best_pct:.0f}% reduction)                       ║",
        f"║  Micro latency add: +{best_micro_ms:.0f}ms avg                                  ║",
        f"║  Net latency delta: {lat_delta:+.1f}s avg                                     ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    """Run full comparison: Section A (classifier accuracy) + Section B (pipeline)."""
    client = OpenAI()
    simple_cases = load_simple_cases()

    # Classifiers for Section A
    clf05 = MicroClassifier("qwen2.5:0.5b")
    clf3b = MicroClassifier("qwen2.5:3b")

    # Pipelines for Section B
    day9 = MultiStagePipeline(client)
    pipe05 = MicroFirstPipeline(client, micro_model="qwen2.5:0.5b")
    pipe3b = MicroFirstPipeline(client, micro_model="qwen2.5:3b")

    all_res05: list = []
    all_res3b: list = []
    all_expected: list[bool] = []
    unsure_fixed_05 = 0
    unsure_fixed_3b = 0

    # ── Section A ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SECTION A — Micro-model accuracy as standalone classifiers")
    print("=" * 70)

    simple_expected = [True] * 10

    r05, r3b = run_classifier_accuracy(clf05, clf3b, simple_cases, simple_expected, "Простые")
    all_res05.extend(r05); all_res3b.extend(r3b); all_expected.extend(simple_expected)

    r05, r3b = run_classifier_accuracy(clf05, clf3b, EDGE_CASES, EDGE_EXPECTED, "Пограничные")
    all_res05.extend(r05); all_res3b.extend(r3b); all_expected.extend(EDGE_EXPECTED)

    r05, r3b = run_classifier_accuracy(clf05, clf3b, NOISY_CASES, NOISY_EXPECTED, "Шумные (не вакансии)")
    all_res05.extend(r05); all_res3b.extend(r3b); all_expected.extend(NOISY_EXPECTED)

    total = len(all_expected)
    acc05 = sum(1 for r, e in zip(all_res05, all_expected) if r.is_vacancy == e)
    acc3b = sum(1 for r, e in zip(all_res3b, all_expected) if r.is_vacancy == e)
    unsure05 = sum(1 for r in all_res05 if r.confidence == "UNSURE")
    unsure3b = sum(1 for r in all_res3b if r.confidence == "UNSURE")
    lat05 = sum(r.latency_ms for r in all_res05) / total
    lat3b = sum(r.latency_ms for r in all_res3b) / total

    print(f"\n--- Итого классификаторы ---")
    print(f"qwen2.5:0.5b  accuracy={acc05}/{total} ({acc05/total*100:.0f}%)  UNSURE={unsure05} ({unsure05/total*100:.0f}%)  avg={lat05:.0f}ms")
    print(f"qwen2.5:3b    accuracy={acc3b}/{total} ({acc3b/total*100:.0f}%)  UNSURE={unsure3b} ({unsure3b/total*100:.0f}%)  avg={lat3b:.0f}ms")

    # ── Section B ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SECTION B — Pipeline comparison (Day9 vs 0.5b-first vs 3b-first)")
    print("=" * 70)

    run_pipeline_comparison(day9, pipe05, pipe3b, "Простые", simple_cases)
    run_pipeline_comparison(day9, pipe05, pipe3b, "Пограничные", EDGE_CASES)
    run_pipeline_comparison(day9, pipe05, pipe3b, "Шумные", NOISY_CASES)

    print("\n")
    day9.print_metrics()
    print()
    pipe05.print_metrics()
    print()
    pipe3b.print_metrics()

    # Count how many UNSURE cases cloud Stage 1 "fixed" (correctly classified)
    for r, e in zip(all_res05, all_expected):
        if r.confidence == "UNSURE" and r.is_vacancy != e:
            unsure_fixed_05 += 1
    for r, e in zip(all_res3b, all_expected):
        if r.confidence == "UNSURE" and r.is_vacancy != e:
            unsure_fixed_3b += 1

    report = build_report(day9, pipe05, pipe3b, all_res05, all_res3b, all_expected,
                          unsure_fixed_05, unsure_fixed_3b)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport saved → {REPORT_PATH}")


if __name__ == "__main__":
    main()
