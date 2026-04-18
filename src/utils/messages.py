"""User-facing message strings used across handlers and services."""

HELP_TEXT: str = (
    "Привет! Я твой персональный AI-ассистент.\n\n"
    "Просто напиши мне сообщение, и я отвечу.\n\n"
    "Команды:\n"
    "/start — приветствие\n"
    "/help — эта справка\n"
    "/reset — сбросить историю диалога\n"
    "/new_chat — начать новый диалог\n"
    "/history — последние 5 сообщений диалога\n"
    "/stats — твоя статистика"
)

RESET_SUCCESS: str = "История диалога сброшена. Начинаем заново!"

NEW_CHAT_STARTED: str = "Начинаю новый диалог. Контекст предыдущего разговора очищен."

NEW_CHAT_NO_PREVIOUS: str = "Новый диалог начат."

EMPTY_MESSAGE_PROMPT: str = "Пожалуйста, введите текст."

LLM_ERROR_FALLBACK: str = "Произошла ошибка при обращении к AI. Попробуй позже."

STATS_TEXT: str = (
    "Твоя статистика:\n\n"
    "Диалогов: {conversation_count}\n"
    "Сообщений: {message_count}\n"
    "Первое сообщение: {first_message_date}"
)

STATS_NO_HISTORY: str = "У тебя ещё нет сообщений. Напиши что-нибудь!"

INTERNAL_ERROR_MESSAGE: str = "Произошла внутренняя ошибка."

HISTORY_NO_MESSAGES: str = "История пуста. Начни диалог — напиши что-нибудь!"

HISTORY_USER_PREFIX: str = "👤"
HISTORY_ASSISTANT_PREFIX: str = "🤖"
