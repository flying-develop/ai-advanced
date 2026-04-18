"""Entry point — creates Bot, Dispatcher, registers middleware and routers, starts polling."""

# stdlib
import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict

# third-party
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# local
from src.config import settings
from src.di import build_conversation_service, build_llm_service, build_session_pool
from src.handlers import assistant_router, start_router, stats_router
from src.middlewares.auth import AuthMiddleware
from src.middlewares.db_session import DbSessionMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class ServiceInjectMiddleware:
    """Middleware that resolves per-request services from the DI factory and injects them."""

    def __init__(self, llm_service: Any) -> None:
        self._llm_service = llm_service

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        data["conversation_service"] = build_conversation_service(
            session=session,
            llm_service=self._llm_service,
        )
        return await handler(event, data)


async def main() -> None:
    """Initialize all components and start long-polling."""
    # Ensure data directory exists for SQLite file
    Path("data").mkdir(exist_ok=True)

    session_pool = build_session_pool()
    llm_service = build_llm_service()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Outer → inner: auth → db_session → service_inject → handlers
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.middleware(DbSessionMiddleware(session_pool=session_pool))
    dp.update.middleware(ServiceInjectMiddleware(llm_service=llm_service))

    # Register routers (order matters: commands before plain-text assistant)
    dp.include_router(start_router)
    dp.include_router(stats_router)
    dp.include_router(assistant_router)

    logger.info("Starting bot polling…")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
