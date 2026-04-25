"""Compare monolithic (Day 7) vs multi-stage (Day 9) pipeline on 30 vacancies."""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_scripts = Path(__file__).parent.parent
_multistage = Path(__file__).parent
for _p in [str(_scripts), str(_multistage)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from inference_pipeline import InferencePipeline
from pipeline import MultiStagePipeline

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

EVAL_FILE = Path("finetuning/data/eval.jsonl")
REPORT_PATH = Path("docs/day9/day9-report.md")

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


def run_category(
    mono: InferencePipeline,
    multi: MultiStagePipeline,
    label: str,
    cases: list[str],
    mono_violations: list[int],
    multi_violations: list[int],
) -> None:
    """Run both pipelines on all cases and print comparison per item."""
    print(f"\n=== Категория: {label} ===")
    for i, text in enumerate(cases, 1):
        mr = mono.process(text)
        ms = multi.process(text)

        mono_violations.append(len(mr.constraint_violations))
        multi_violations.append(len(ms.constraint_violations))

        mono_score = f" score={mr.confidence_score:.2f}" if mr.final_status != "FAIL" else ""
        mono_str = f"Monolithic: {mr.final_status:<4}{mono_score} calls={mr.api_calls_made} {mr.latency_ms/1000:.1f}s"

        if ms.final_status == "SKIP":
            multi_str = f"Multi-stage: SKIP  calls={ms.total_api_calls} {ms.latency_ms/1000:.1f}s ({ms.skip_reason})"
        else:
            multi_str = (
                f"Multi-stage: {ms.final_status:<4} calls={ms.total_api_calls} "
                f"{ms.latency_ms/1000:.1f}s tokens={ms.total_tokens}"
            )

        print(f"[{i:2d}/{len(cases)}] {mono_str} | {multi_str}")


def build_report(mono: InferencePipeline, multi: MultiStagePipeline,
                 mono_violations_total: int, multi_violations_total: int) -> str:
    """Build ASCII comparison report."""
    mm = mono.get_metrics()
    ms = multi.get_metrics()
    mt = mm["total"] or 1
    st = ms["total"] or 1

    mono_ok_pct = mm["ok_count"] / mt * 100
    mono_fail_pct = mm["fail_count"] / mt * 100
    multi_ok_pct = ms["ok_count"] / st * 100
    multi_skip_pct = ms["skip_count"] / st * 100
    multi_fail_pct = ms["fail_count"] / st * 100

    mono_lat = mm["avg_latency_ms"] / 1000
    multi_lat = ms["avg_latency_ms"] / 1000
    lat_delta = multi_lat - mono_lat

    calls_saved = ms["skip_count"] * 2  # skipped cases avoid Stage 2+3

    lines = [
        "# Comparison Report — Day 9\n",
        "```",
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║                    COMPARISON REPORT — DAY 9                         ║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        "║                        MONOLITHIC (Day 7)                            ║",
        f"║  OK:           {mm['ok_count']:<3} ({mono_ok_pct:.0f}%){'':49}║",
        f"║  FAIL:         {mm['fail_count']:<3} ({mono_fail_pct:.0f}%){'':49}║",
        f"║  API calls:    {mm['total_api_calls']:<6} total | {mm['avg_calls_per_request']:.1f} avg per request{'':27}║",
        f"║  Avg latency:  {mono_lat:.1f}s{'':56}║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        "║                        MULTI-STAGE (Day 9)                           ║",
        f"║  OK:           {ms['ok_count']:<3} ({multi_ok_pct:.0f}%){'':49}║",
        f"║  SKIP:         {ms['skip_count']:<3} ({multi_skip_pct:.0f}%) — filtered at Stage 1 (not vacancy){'':14}║",
        f"║  FAIL:         {ms['fail_count']:<3} ({multi_fail_pct:.0f}%){'':49}║",
        f"║  API calls:    {ms['total_api_calls']:<6} total | {ms['avg_calls']:.1f} avg per request{'':27}║",
        f"║  Avg latency:  {multi_lat:.1f}s{'':56}║",
        f"║  Total tokens: {ms['total_tokens']:<6} | {ms['avg_tokens']:.0f} avg per request{'':30}║",
        "╠══════════════════════════════════════════════════════════════════════╣",
        "║                        DELTA                                         ║",
        f"║  Calls saved by Stage 1 filter:  {calls_saved:<38}║",
        f"║  Latency overhead (multi vs mono): {lat_delta:+.1f}s avg{'':33}║",
        "║  Constraint violations:                                              ║",
        f"║    Monolithic:   {mono_violations_total:<55}║",
        f"║    Multi-stage:  {multi_violations_total:<55}║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    """Run comparison on 30 vacancies and save report."""
    client = OpenAI()
    mono = InferencePipeline(client)
    multi = MultiStagePipeline(client)

    simple_cases = load_simple_cases()

    mono_violations: list[int] = []
    multi_violations: list[int] = []

    run_category(mono, multi, "Простые", simple_cases, mono_violations, multi_violations)
    run_category(mono, multi, "Пограничные", EDGE_CASES, mono_violations, multi_violations)
    run_category(mono, multi, "Сложные/шумные", NOISY_CASES, mono_violations, multi_violations)

    print("\n")
    mono.print_metrics()
    print()
    multi.print_metrics()

    report = build_report(mono, multi, sum(mono_violations), sum(multi_violations))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport saved → {REPORT_PATH}")


if __name__ == "__main__":
    main()
