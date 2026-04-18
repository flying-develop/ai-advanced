# ADR-001: Выбор aiogram 3.x

**Статус:** Принято  
**Дата:** 2026-04-18

## Context

Нужен Python-фреймворк для Telegram-бота с поддержкой async I/O, middleware pipeline и роутеров. Рассматривались: aiogram 3.x, python-telegram-bot 20.x, Telethon.

## Decision

**aiogram 3.x** — async-first с нуля, гибкие `Router`, встроенный middleware pipeline с явным порядком, DI через `data` dict, `dp.errors()` для глобального error handling.

**Отклонено:**
- `python-telegram-bot` — sync-legacy в async-обёртке, нет Router
- `Telethon` — MTProto user-client, не Bot API, нет middleware

## Consequences

**+** Чистая трёхслойная архитектура (Handler→Service→Repository), изолированный контекст на каждый Update.  
**−** Breaking changes при мажорных обновлениях, неполная документация v3.
