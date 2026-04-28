"""/indirect_demo command handler — runs 3-scenario indirect injection demo."""

# stdlib
import logging

# third-party
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

# local
from src.services.indirect_injection.demo_runner import IndirectInjectionDemoRunner

logger = logging.getLogger(__name__)

indirect_demo_router = Router(name="indirect_demo")


@indirect_demo_router.message(Command("indirect_demo"))
async def cmd_indirect_demo(
    message: Message,
    demo_runner: IndirectInjectionDemoRunner | None = None,
) -> None:
    """Run the 3-scenario indirect injection demo and send results to the user."""
    if demo_runner is None:
        await message.answer(
            "⚠️ Indirect demo отключён. Установи INDIRECT_DEMO_ENABLED=true в .env"
        )
        return

    await message.answer(
        "🔬 Запускаю демо Indirect Prompt Injection...\n"
        "Тестирую 3 вектора атаки (без защиты → с защитой)\n"
        "⏳ Это займёт ~30 секунд (6 LLM-запросов)"
    )

    results = await demo_runner.run_all()

    for r in results:
        unprotected_status = "✅ ПРОШЛА" if r.attack_succeeded_unprotected else "❌ НЕ ПРОШЛА"
        protected_status = "✅ ПРОШЛА" if r.attack_succeeded_protected else "❌ заблокирована"

        text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>{r.scenario_name}</b>\n\n"
            f"<b>БЕЗ защиты:</b> атака {unprotected_status}\n"
            f"<code>{r.unprotected_response[:300]}"
            f"{'...' if len(r.unprotected_response) > 300 else ''}</code>\n\n"
            f"<b>С защитой ({', '.join(r.defense_layers_applied[:2])}):</b>"
            f" атака {protected_status}\n"
            f"<code>{r.protected_response[:300]}"
            f"{'...' if len(r.protected_response) > 300 else ''}</code>\n"
        )

        if r.output_violations_unprotected:
            text += (
                f"\n⚠️ <b>Нарушения найдены:</b> "
                f"{'; '.join(r.output_violations_unprotected)}"
            )

        await message.answer(text, parse_mode='HTML')

    total = len(results)
    bypassed = sum(1 for r in results if r.attack_succeeded_protected)
    await message.answer(
        f"📊 <b>Итог:</b>\n"
        f"Атак всего: {total}\n"
        f"Прошли после защиты: {bypassed}/{total}\n"
        f"Заблокировано: {total - bypassed}/{total}",
        parse_mode='HTML',
    )
