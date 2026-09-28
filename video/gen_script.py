"""Демо-сценарий для ролика: прогон через настоящие обработчики бота (tg_mock.py подменяет только Telegram).
Запуск из корня проекта: .venv\\Scripts\\python video\\gen_script.py"""
import asyncio
import os
import sys
from pathlib import Path

import aiosqlite

VIDEO = Path(__file__).resolve().parent
ROOT = VIDEO.parent
sys.path[:0] = [str(ROOT), str(VIDEO)]
os.chdir(ROOT)

import config  # noqa: E402

SELLER = 2000
config.DB_PATH = "video_demo.db"   # отдельная временная БД, живую не трогаем
config.ALLOWED_IDS.clear()

import db  # noqa: E402
import monitor  # noqa: E402
from handlers import main as main_handlers  # noqa: E402
from tg_mock import TgDemo  # noqa: E402

MINE_A, MINE_B = 608351566, 839226871
RIVALS = [604961294, 1470151551, 1453309500]
STAGED = 1470151551  # у этого конкурента для демо уведомления завышаем прошлую цену
A, B = "⬜ Наушники беспроводные для", "⬜ Наушники беспроводные TWS"


async def main():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    await db.init()
    d = TgDemo([main_handlers.router], bot_name="WB Радар", chats={SELLER: ("Иван", "Селлер")},
               media_dir=VIDEO / "public" / "media")
    u = SELLER
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
        # Демо уведомления: прошлая цена конкурента в базе завышена, дальше — настоящая проверка
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute("UPDATE products SET price = round(price * 1.25) WHERE nm=?", (STAGED,))
            await conn.commit()
        d.clock("очередная проверка цен")
        await monitor.check_all(d.bot)
        await d.say(u, "📊 Сводка")
        await d.say(u, "📥 Excel")
    finally:
        if os.path.exists(config.DB_PATH):
            os.remove(config.DB_PATH)
    d.save(VIDEO / "src" / "data" / "script.json")


if __name__ == "__main__":
    asyncio.run(main())
