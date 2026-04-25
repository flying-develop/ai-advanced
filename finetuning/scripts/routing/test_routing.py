"""Test routing pipeline on 30 vacancies: 10 simple, 10 edge, 10 noisy."""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_scripts = Path(__file__).parent.parent
_routing = Path(__file__).parent
for _p in [str(_scripts), str(_routing)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from model_router import ModelRouter
from routed_pipeline import RoutedPipeline, RoutedResult

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EVAL_FILE = Path("finetuning/data/eval.jsonl")
REPORT_PATH = Path("docs/day8/day8-report.md")

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


def _route_label(result: RoutedResult) -> str:
    """Format route string for output."""
    if result.initial_model == ModelRouter.TIER1_MODEL:
        if result.escalated:
            return "mini→gpt4"
        return "mini→OK" if result.final_status == "OK" else "mini→FAIL"
    return "gpt4→OK" if result.final_status == "OK" else "gpt4→FAIL"


def run_category(pipeline: RoutedPipeline, label: str, cases: list[str]) -> list[dict]:
    """Run pipeline on all cases in a category and print per-item results."""
    print(f"\n=== Категория: {label} ===")
    results = []
    for i, text in enumerate(cases, 1):
        result = pipeline.process(text)
        route = _route_label(result)
        latency_s = result.latency_ms / 1000
        esc_info = f" | escalated: {result.escalation_reason}" if result.escalated else ""
        print(
            f"[{i:2d}/{len(cases)}] {result.final_status:<4} | "
            f"{route:<10} | "
            f"score={result.confidence_score:.2f} | "
            f"calls={result.total_calls} ({result.tier1_calls}+{result.tier2_calls}) | "
            f"{latency_s:.1f}s"
            f"{esc_info}"
        )
        results.append(
            {
                "index": i,
                "category": label,
                "status": result.final_status,
                "route": route,
                "score": result.confidence_score,
                "tier1_calls": result.tier1_calls,
                "tier2_calls": result.tier2_calls,
                "total_calls": result.total_calls,
                "latency_s": latency_s,
                "escalated": result.escalated,
                "escalation_reason": result.escalation_reason,
            }
        )
    return results


def build_report(pipeline: RoutedPipeline) -> str:
    """Build ASCII report string."""
    m = pipeline.get_metrics()
    total = m["total"] or 1
    ok_pct = m["ok_count"] / total * 100
    fail_pct = m["fail_count"] / total * 100
    tier1_pct = m["tier1_only"] / total * 100
    esc_pct = m["escalated_count"] / total * 100
    esc_ok_pct = m["escalated_ok"] / max(m["escalated_count"], 1) * 100
    avg_latency_s = m["avg_latency_ms"] / 1000

    lines = [
        "# Routing Report — Day 8\n",
        "```",
        "╔══════════════════════════════════════════════════════════════╗",
        "║              ROUTING REPORT — DAY 8                          ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Total processed:          {m['total']:<36}║",
        f"║ OK:                       {m['ok_count']:<3} ({ok_pct:.0f}%){'':31}║",
        f"║ FAIL:                     {m['fail_count']:<3} ({fail_pct:.0f}%){'':31}║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Stayed on gpt-4o-mini:    {m['tier1_only']:<3} ({tier1_pct:.0f}%) — tier1 only{'':17}║",
        f"║ Escalated to gpt-4o:      {m['escalated_count']:<3} ({esc_pct:.0f}%){'':31}║",
        f"║   └─ rescued after esc.:  {m['escalated_ok']:<3} ({esc_ok_pct:.0f}% of escalated){'':17}║",
        f"║   └─ failed after esc.:   {m['escalated_fail']:<36}║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║ Total API calls:          {m['total_calls']:<36}║",
        f"║   Tier 1 (mini) calls:    {m['total_tier1_calls']:<36}║",
        f"║   Tier 2 (gpt-4o) calls:  {m['total_tier2_calls']:<36}║",
        f"║ Avg calls per request:    {m['avg_calls']:.1f}{'':34}║",
        f"║ Avg latency:              {avg_latency_s:.1f}s{'':33}║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║ vs Day 7 self-check:                                         ║",
        "║   Day 7 total calls:      [вставь вручную из day7-report]   ║",
        f"║   Day 8 total calls:      {m['total_calls']:<36}║",
        "║   Разница:                [вставь вручную]                  ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    """Run all 30 test cases and save report."""
    client = OpenAI()
    pipeline = RoutedPipeline(client)

    simple_cases = load_simple_cases()

    run_category(pipeline, "Простые", simple_cases)
    run_category(pipeline, "Пограничные", EDGE_CASES)
    run_category(pipeline, "Сложные/шумные", NOISY_CASES)

    print("\n")
    pipeline.print_metrics()

    report_text = build_report(pipeline)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"\nReport saved → {REPORT_PATH}")


if __name__ == "__main__":
    main()
