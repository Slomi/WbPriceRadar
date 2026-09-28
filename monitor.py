"""Периодическая проверка цен и остатков, уведомления и ежедневный отчёт."""
import asyncio
import logging
from datetime import datetime, timezone
from html import escape

from aiogram import Bot

import config
import db
import reports
import wb
from utils import now, rub, short

_check_lock = asyncio.Lock()


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def seed_history(card: wb.Card) -> None:
    """Для нового артикула: недельная история с сайта WB + первая точка наших проверок."""
    if not await db.has_wb_history(card.nm):
        for dt, price in await wb.fetch_price_history(card.nm):
            await db.add_history(card.nm, dt.replace(microsecond=0).isoformat(), price, None, "wb")
    await db.add_history(card.nm, utc_iso(), card.price, card.qty, "bot")


def _pct(old: float, new: float) -> float:
    return (new - old) / old * 100 if old else 0.0


async def _alerts_for(p, card: wb.Card, user) -> list[str]:
    """Что изменилось у товара p (строка из БД со старыми значениями) по сравнению со свежей карточкой."""
    out: list[str] = []
    title = f"<b>{escape(card.name[:60])}</b> (<a href=\"{card.url}\">{card.nm}</a>)"
    who = "⭐ Ваш товар" if p["role"] == "mine" else "🎯 Конкурент"

    old, new = p["price"], card.price
    if old and new and old != new and abs(_pct(old, new)) >= user["price_pct"]:
        arrow = "📉 подешевел" if new < old else "📈 подорожал"
        line = f"{who} {arrow}: {rub(old)} → <b>{rub(new)}</b> ({_pct(old, new):+.0f}%)\n{title}"
        if p["role"] == "rival":
            mines = [m for m in await db.mines_of(p["id"]) if m["price"]]
            for mine in mines:
                diff = new - mine["price"]
                name = f" «{escape(short(mine['name'], 30))}»" if len(mines) > 1 else ""
                if diff < 0:
                    line += f"\n⚠️ Теперь дешевле вашего товара{name} на <b>{rub(-diff)}</b>"
                elif diff > 0:
                    line += f"\nВаш товар{name} дешевле на {rub(diff)}"
        out.append(line)

    if p["qty"] is not None:
        if p["qty"] > 0 and card.qty == 0:
            out.append(f"{who}: ❌ <b>закончился</b>\n{title}"
                       + ("\n💡 У конкурента дефицит — можно пересмотреть цену" if p["role"] == "rival" else ""))
        elif p["qty"] == 0 and card.qty > 0:
            out.append(f"{who}: ✅ <b>снова в наличии</b> ({card.qty} шт)\n{title}")
        elif p["qty"] >= user["stock_low"] > card.qty > 0:
            out.append(f"{who}: ⚠️ заканчивается — осталось <b>{card.qty} шт</b>\n{title}")
    return out


async def check_all(bot: Bot | None = None) -> int:
    """Проверяет все артикулы всех пользователей. Возвращает число отправленных уведомлений."""
    async with _check_lock:
        nms = await db.all_nms()
        if not nms:
            return 0
        cards = await wb.fetch_cards(nms)
        ts = utc_iso()
        by_user: dict[int, list[str]] = {}
        for nm, card in cards.items():
            await db.add_history(nm, ts, card.price, card.qty, "bot")
            for p in await db.products_by_nm(nm):
                user = await db.get_user(p["user_id"])
                by_user.setdefault(p["user_id"], []).extend(await _alerts_for(p, card, user))
                await db.update_product_state(p["id"], card)
        sent = 0
        if bot:
            for user_id, alerts in by_user.items():
                for chunk_start in range(0, len(alerts), 10):
                    try:
                        await bot.send_message(user_id, "\n\n".join(alerts[chunk_start:chunk_start + 10]),
                                               disable_web_page_preview=True)
                        sent += 1
                    except Exception:
                        logging.exception("Не удалось отправить уведомление %s", user_id)
        return sent


async def send_daily_reports(bot: Bot) -> None:
    current = now()
    today = current.date().isoformat()
    for user in await db.users_with_products():
        if user["report_hour"] == current.hour and user["last_report"] != today:
            try:
                await bot.send_message(user["user_id"], await reports.daily_report(user["user_id"]),
                                       disable_web_page_preview=True)
            except Exception:
                logging.exception("Не удалось отправить отчёт %s", user["user_id"])
            await db.set_user(user["user_id"], last_report=today)


async def loop(bot: Bot) -> None:
    last_check = 0.0
    while True:
        try:
            loop_time = asyncio.get_running_loop().time()
            if loop_time - last_check >= config.CHECK_INTERVAL_MIN * 60:
                last_check = loop_time
                n = await check_all(bot)
                logging.info("Проверка цен завершена, уведомлений: %s", n)
            await send_daily_reports(bot)
        except Exception:
            logging.exception("Ошибка в цикле мониторинга")
        await asyncio.sleep(60)
