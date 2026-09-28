"""Прогоняет демо-сценарий через НАСТОЯЩИЕ обработчики бота (aiogram + GigaChat),
подменяя только транспорт Telegram. Все ответы бота записываются в public/script.json для ролика.
Запуск из корня проекта: .venv\\Scripts\\python video\\gen_script.py"""
import asyncio
import json
import os
import sys
import time

import aiosqlite
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import config  # noqa: E402

CLIENT_ID, ADMIN_ID, BOT_ID = 2000, 1000, 9999
config.DB_PATH = "video_demo.db"
config.ALLOWED_IDS.clear()

import db  # noqa: E402

db.DB_PATH = config.DB_PATH
from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.types import (InlineKeyboardMarkup, Message, MessageId, ReplyKeyboardMarkup,  # noqa: E402
                           ReplyKeyboardRemove, Update)

from handlers import main as main_handlers  # noqa: E402
import monitor  # noqa: E402

EVENTS: list[dict] = []
MEDIA_DIR = Path(__file__).parent / "public" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES: dict[tuple[int, int], dict] = {}   # (chat, id) -> сырое сообщение (для кнопок и reply)
USERS = {CLIENT_ID: {"id": CLIENT_ID, "is_bot": False, "first_name": "Иван"},
         ADMIN_ID: {"id": ADMIN_ID, "is_bot": False, "first_name": "Мастер"}}
BOT_USER = {"id": BOT_ID, "is_bot": True, "first_name": "ЦенаРадар"}


def dump_markup(m):
    if isinstance(m, InlineKeyboardMarkup):
        return {"inline": [[b.text for b in row] for row in m.inline_keyboard]}
    if isinstance(m, ReplyKeyboardMarkup):
        return {"reply": [[b.text for b in row] for row in m.keyboard]}
    if isinstance(m, ReplyKeyboardRemove):
        return {"remove": True}
    return None


class MockSession(BaseSession):
    """Вместо HTTP к Telegram — запись того, что бот отправил."""

    def __init__(self):
        super().__init__()
        self._id = 500

    def new_id(self) -> int:
        self._id += 1
        return self._id

    def msg(self, bot, chat_id, mid, text, from_user=BOT_USER, markup=None, reply_to=None):
        data = {"message_id": mid, "date": int(time.time()), "chat": {"id": chat_id, "type": "private"},
                "from": from_user, "text": text}
        if markup is not None:
            data["reply_markup"] = markup.model_dump(exclude_none=True)
        if reply_to:
            data["reply_to_message"] = reply_to
        return Message.model_validate(data, context={"bot": bot}), data

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        if name == "SendMessage":
            mid = self.new_id()
            inline = method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None
            m, data = self.msg(bot, method.chat_id, mid, method.text, markup=inline)
            MESSAGES[(method.chat_id, mid)] = data
            EVENTS.append({"op": "bot", "chat": method.chat_id, "id": mid, "text": method.text,
                           "markup": dump_markup(method.reply_markup)})
            return m
        if name == "EditMessageText":
            data = MESSAGES[(method.chat_id, method.message_id)]
            data["text"] = method.text
            if isinstance(method.reply_markup, InlineKeyboardMarkup):
                data["reply_markup"] = method.reply_markup.model_dump(exclude_none=True)
            else:
                data.pop("reply_markup", None)
            EVENTS.append({"op": "edit", "chat": method.chat_id, "id": method.message_id, "text": method.text,
                           "markup": dump_markup(method.reply_markup)})
            m, _ = self.msg(bot, method.chat_id, method.message_id, method.text)
            return m
        if name == "CopyMessage":
            src = MESSAGES[(method.from_chat_id, method.message_id)]
            mid = self.new_id()
            EVENTS.append({"op": "bot", "chat": method.chat_id, "id": mid, "text": src["text"], "markup": None})
            return MessageId(message_id=mid)
        if name == "EditMessageReplyMarkup":
            EVENTS.append({"op": "edit_markup", "chat": method.chat_id, "id": method.message_id,
                           "markup": dump_markup(method.reply_markup)})
            m, _ = self.msg(bot, method.chat_id, method.message_id, MESSAGES[(method.chat_id, method.message_id)]["text"])
            return m
        if name in ("SendPhoto", "SendDocument"):
            mid = self.new_id()
            media = method.photo if name == "SendPhoto" else method.document
            fname = f"{mid}_{media.filename}"
            (MEDIA_DIR / fname).write_bytes(media.data)
            EVENTS.append({"op": "photo" if name == "SendPhoto" else "document", "chat": method.chat_id, "id": mid,
                           "file": fname, "text": method.caption or "", "markup": None})
            m, data = self.msg(bot, method.chat_id, mid, method.caption or "")
            MESSAGES[(method.chat_id, mid)] = data
            return m
        if name == "AnswerCallbackQuery":
            if method.text:
                EVENTS.append({"op": "toast", "chat": None, "text": method.text})
            return True
        if name in ("SendChatAction", "SetMyCommands", "DeleteWebhook"):
            return True
        raise RuntimeError(f"Не замокан метод {name}")

    async def close(self):
        pass

    async def stream_content(self, *a, **kw):
        raise RuntimeError("не нужно")


class Demo:
    def __init__(self):
        self.session = MockSession()
        self.bot = Bot("1:demo", session=self.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dp = Dispatcher()
        self.dp.include_router(main_handlers.router)
        self.upd = 0

    async def feed(self, payload: dict):
        self.upd += 1
        update = Update.model_validate({"update_id": self.upd, **payload}, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)

    async def say(self, uid: int, text: str, reply_to_id: int | None = None):
        mid = self.session.new_id()
        reply_to = MESSAGES.get((uid, reply_to_id)) if reply_to_id else None
        _, data = self.session.msg(self.bot, uid, mid, text, from_user=USERS[uid], reply_to=reply_to)
        MESSAGES[(uid, mid)] = data
        EVENTS.append({"op": "user", "chat": uid, "id": mid, "text": text, "reply_to": reply_to_id})
        await self.feed({"message": data})

    async def click(self, uid: int, prefix: str) -> bool:
        """Жмёт последнюю по времени inline-кнопку с таким началом текста."""
        for (chat, mid), data in sorted(MESSAGES.items(), key=lambda kv: -kv[0][1]):
            if chat != uid or "reply_markup" not in data:
                continue
            for row in data["reply_markup"].get("inline_keyboard", []):
                for b in row:
                    if b["text"].startswith(prefix):
                        EVENTS.append({"op": "click", "chat": uid, "id": mid, "button": b["text"]})
                        await self.feed({"callback_query": {
                            "id": str(self.upd), "from": USERS[uid], "chat_instance": "demo",
                            "message": data, "data": b["callback_data"]}})
                        return True
        return False

    def last_admin_notice(self, starts: str) -> int:
        return next(e["id"] for e in reversed(EVENTS)
                    if e.get("chat") == ADMIN_ID and e["op"] == "bot" and e["text"].startswith(starts))


MINE_A, MINE_B = 608351566, 839226871
RIVALS = [604961294, 1470151551, 1453309500]
STAGED = 1470151551  # у этого конкурента для демо уведомления завышаем прошлую цену
A, B = "⬜ Наушники беспроводные для", "⬜ Наушники беспроводные TWS"


async def main():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    await db.init()
    d = Demo()
    u = CLIENT_ID
    try:
        await d.say(u, "/start")
        await d.say(u, "➕ Добавить товар")
        await d.say(u, f"https://www.wildberries.ru/catalog/{MINE_A}/detail.aspx {MINE_B}")
        await d.click(u, "⭐ Это мои")
        await d.say(u, " ".join(map(str, RIVALS)))
        await d.click(u, "🎯 Это конкуренты")
        await d.click(u, "🧩")
        await d.click(u, A)                    # 1-й конкурент → товар A
        await d.click(u, "Далее")
        await d.click(u, A)                    # 2-й → A и B
        await d.click(u, B)
        await d.click(u, "Далее")
        await d.click(u, B)                    # 3-й → B
        await d.click(u, "✅ Готово")
        await d.say(u, "📋 Мои товары")
        await d.click(u, "⭐ ")
        await d.click(u, "📈")
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute("UPDATE products SET price = round(price * 1.25) WHERE nm=?", (STAGED,))
            await conn.commit()
        EVENTS.append({"op": "clock", "chat": None, "text": "очередная проверка цен"})
        await monitor.check_all(d.bot)
        await d.say(u, "📊 Сводка")
        await d.say(u, "📥 Excel")
    finally:
        if os.path.exists(config.DB_PATH):
            os.remove(config.DB_PATH)

    out = Path(__file__).parent / "src" / "data" / "script.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"client": CLIENT_ID, "admin": ADMIN_ID, "events": EVENTS},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"событий: {len(EVENTS)} → {out}")


if __name__ == "__main__":
    asyncio.run(main())
