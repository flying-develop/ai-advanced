"""Test inference pipeline on 30 vacancies: 10 simple, 10 edge cases, 10 noisy."""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from inference_pipeline import InferencePipeline

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EVAL_FILE = Path("finetuning/data/eval.jsonl")

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

REPORT_PATH = Path("docs/day7/day7-report.md")


def load_simple_cases() -> list[str]:
    """Load first 10 vacancy texts from eval.jsonl."""
    cases = []
    with EVAL_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            messages = record.get("messages", [])
            for msg in messages:
                if msg.get("role") == "user":
                    cases.append(msg["content"])
                    break
            if len(cases) >= 10:
                break
    return cases


def run_category(pipeline: InferencePipeline, label: str, cases: list[str]) -> list[dict]:
    """Run pipeline on all cases in a category and print per-item results."""
    print(f"\n=== Категория: {label} ===")
    results = []
    for i, text in enumerate(cases, 1):
        result = pipeline.process(text)
        self_info = ""
        if result.self_check_triggered:
            self_info = f" | self-check → {result.final_status}"
        latency_s = result.latency_ms / 1000
        print(
            f"[{i:2d}/{len(cases)}] {result.final_status:<6} | "
            f"score={result.confidence_score:.2f} | "
            f"calls={result.api_calls_made} | "
            f"{latency_s:.1f}s"
            f"{self_info}"
        )
        results.append(
            {
                "index": i,
                "category": label,
                "status": result.final_status,
                "score": result.confidence_score,
                "calls": result.api_calls_made,
                "latency_s": latency_s,
                "self_check": result.self_check_triggered,
                "reason": result.reason,
            }
        )
    return results


def build_report(pipeline: InferencePipeline) -> str:
    """Build the ASCII report string."""
    m = pipeline.get_metrics()
    total = m["total"] or 1
    ok_pct = m["ok_count"] / total * 100
    unsure_pct = m["unsure_count"] / total * 100
    fail_pct = m["fail_count"] / total * 100
    avg_latency_s = m["avg_latency_ms"] / 1000

    lines = [
        "# Inference Quality Report — Day 7\n",
        "```",
        "╔══════════════════════════════════════════════════════════╗",
        "║              INFERENCE QUALITY REPORT — DAY 7            ║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║ Total processed:        {m['total']:<34}║",
        f"║ OK:                     {m['ok_count']:<3} ({ok_pct:.0f}%){'':27}║",
        f"║ UNSURE:                 {m['unsure_count']:<3} ({unsure_pct:.0f}%){'':27}║",
        f"║ FAIL:                   {m['fail_count']:<3} ({fail_pct:.0f}%){'':27}║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║ Self-check triggered:   {m['self_check_triggered']:<34}║",
        f"║ Self-check rescued:     {m['self_check_rescued']:<3} (UNSURE→OK){'':23}║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║ Total API calls:        {m['total_api_calls']:<34}║",
        f"║ Avg calls per request:  {m['avg_calls_per_request']:.1f}{'':32}║",
        f"║ Avg latency:            {avg_latency_s:.1f}s{'':31}║",
        "╚══════════════════════════════════════════════════════════╝",
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    """Run all 30 test cases and save report."""
    client = OpenAI()
    pipeline = InferencePipeline(client)

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
