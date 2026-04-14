"""DbSessionMiddleware — injects an AsyncSession into each handler's kwargs."""

# stdlib
import logging
from typing import Any, Awaitable, Callable, Dict

# third-party
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """Opens a DB session per update, commits on success, rolls back on error."""

    def __init__(self, session_pool: async_sessionmaker) -> None:
        self._session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self._session_pool() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
