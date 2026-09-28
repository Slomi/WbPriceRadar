import asyncio
from dataclasses import asdict
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

import config
import db
import keyboards as kb
import monitor
import reports
import wb
from utils import now, rub, short

router = Router()
if config.ALLOWED_IDS:
    router.message.filter(F.from_user.id.in_(config.ALLOWED_IDS))
    router.callback_query.filter(F.from_user.id.in_(config.ALLOWED_IDS))


class Add(StatesGroup):
    links = State()   # ждём ссылки/артикулы
    role = State()    # ждём выбор «мои / конкуренты»


def _cycle(values: list, current):
    return values[(values.index(current) + 1) % len(values)] if current in values else values[0]


# ---------- Старт и меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.get_user(message.from_user.id)
    await message.answer(
        f"Привет, {escape(message.from_user.first_name)}! 👋\n\n"
        "Я слежу за ценами и остатками на <b>Wildberries</b> — вашими и конкурентов:\n"
        f"• проверяю товары каждые {config.CHECK_INTERVAL_MIN} мин и пишу, когда цена изменилась;\n"
        "• предупреждаю, если конкурент стал дешевле вас или у него закончился товар;\n"
        "• присылаю утреннюю сводку, графики истории цен и выгрузку в Excel.\n\n"
        "Начните с кнопки «➕ Добавить товар» — или просто пришлите ссылку на товар WB 👇",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


# ---------- Добавление ----------

@router.message(StateFilter(None), F.text == kb.MENU_ADD)
async def add_start(message: Message, state: FSMContext):
    await state.set_state(Add.links)
    await message.answer("Пришлите ссылки на товары WB или артикулы — можно сразу несколько, через пробел или с новой строки.")


async def _ask_role(message: Message, state: FSMContext, text: str, parent: int | None):
    nms = wb.parse_nms(text)
    if not nms:
        return await message.answer("Не нашёл артикулов. Пример: https://www.wildberries.ru/catalog/839226871/detail.aspx")
    left = config.MAX_PRODUCTS_PER_USER - await db.count_products(message.from_user.id)
    if left <= 0:
        return await message.answer(f"Лимит — {config.MAX_PRODUCTS_PER_USER} товаров. Удалите лишние в «📋 Мои товары».")
    nms = nms[:left]
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        cards = await wb.fetch_cards(nms)
    if not cards:
        return await message.answer("WB не нашёл таких товаров. Проверьте ссылку или артикул.")
    missing = [str(n) for n in nms if n not in cards]
    lines = [f"• {escape(short(c.name, 45))} — <b>{rub(c.price)}</b>" for c in cards.values()]
    text = "Нашёл:\n" + "\n".join(lines) + (f"\n\nНе найдены: {', '.join(missing)}" if missing else "")
    await state.update_data(cards=[asdict(c) for c in cards.values()])
    if parent is not None:  # добавляем конкурентов к выбранному товару без лишних вопросов
        await message.answer(text)
        return await _save(message, state, message.from_user.id, "rival", parent)
    await state.set_state(Add.role)
    mine = [p for p in await db.user_products(message.from_user.id) if p["role"] == "mine"]
    await message.answer(text + "\n\nЧьи это товары?", reply_markup=kb.role_kb(mine))


MENU_ACTIONS = {}  # кнопка меню посреди добавления — отменяем добавление и выполняем её


@router.message(StateFilter(Add), F.text.func(lambda t: t in MENU_ACTIONS))
async def menu_during_add(message: Message, state: FSMContext):
    await state.clear()
    if message.text == kb.MENU_ADD:
        return await add_start(message, state)
    await MENU_ACTIONS[message.text](message)


@router.message(Add.links, F.text)
async def add_links(message: Message, state: FSMContext):
    parent = (await state.get_data()).get("parent")
    await _ask_role(message, state, message.text, parent)


@router.message(StateFilter(None), F.text.regexp(r"\d{5,12}"))
async def add_quick(message: Message, state: FSMContext):
    """Ссылку или артикул можно прислать и без кнопки «Добавить»."""
    await _ask_role(message, state, message.text, None)


async def _save(message: Message, state: FSMContext, user_id: int, role: str, parent: int | None):
    cards = [wb.Card(**c) for c in (await state.get_data()).get("cards", [])]
    await state.clear()
    if not cards:
        return await message.answer("Список устарел — пришлите ссылки ещё раз.", reply_markup=kb.main_menu())
    added, dupes = [], []
    for c in cards:
        pid = await db.add_product(user_id, c, role, parent or None)
        (added if pid else dupes).append(c)
    status = await message.answer("⏳ Загружаю историю цен…")
    await asyncio.gather(*(monitor.seed_history(c) for c in added))
    who = "ваши товары" if role == "mine" else "конкуренты"
    text = f"✅ Добавлено: {len(added)} ({who})."
    if dupes:
        text += f"\nУже были в списке: {len(dupes)}."
    if role == "mine" and added:
        text += "\n\nТеперь добавьте конкурентов: «📋 Мои товары» → ваш товар → «➕ Конкурент»."
    await status.edit_text(text)
    await message.answer("Проверяю цены автоматически — напишу, когда что-то изменится.", reply_markup=kb.main_menu())


@router.callback_query(Add.role, kb.RoleCB.filter())
async def add_role(cb: CallbackQuery, callback_data: kb.RoleCB, state: FSMContext):
    await cb.answer()
    await cb.message.edit_reply_markup(reply_markup=None)
    await _save(cb.message, state, cb.from_user.id, callback_data.role, callback_data.parent or None)


# ---------- Список и карточка ----------

async def _show_list(message: Message, user_id: int, edit: bool = False):
    products = await db.user_products(user_id)
    if not products:
        text, markup = "Список пуст. Добавьте товар кнопкой «➕ Добавить товар».", None
    else:
        mine = sum(p["role"] == "mine" for p in products)
        text = f"📋 <b>Отслеживаю {len(products)}</b>: ваших {mine}, конкурентов {len(products) - mine}.\n❗ — конкурент дешевле вас"
        markup = kb.list_kb(products)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(StateFilter(None), F.text == kb.MENU_LIST)
async def list_products(message: Message):
    await _show_list(message, message.from_user.id)


@router.callback_query(kb.ListCB.filter(F.action == "show"))
async def list_back(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer()
    await _show_list(cb.message, cb.from_user.id, edit=True)


@router.callback_query(kb.ListCB.filter(F.action == "check_all"))
async def check_all(cb: CallbackQuery):
    await cb.answer("Проверяю…")
    sent = await monitor.check_all(cb.bot)
    await _show_list(cb.message, cb.from_user.id, edit=True)
    if not sent:
        await cb.message.answer(f"🔄 Проверено в {now():%H:%M}. Изменений нет.")


@router.callback_query(kb.ProdCB.filter(F.action == "view"))
async def view(cb: CallbackQuery, callback_data: kb.ProdCB):
    p = await db.get_product(callback_data.id, cb.from_user.id)
    if not p:
        return await cb.answer("Товар уже удалён", show_alert=True)
    await cb.answer()
    await cb.message.edit_text(await reports.card_text(p), reply_markup=kb.product_kb(p), disable_web_page_preview=True)


@router.callback_query(kb.ProdCB.filter(F.action == "refresh"))
async def refresh(cb: CallbackQuery, callback_data: kb.ProdCB):
    p = await db.get_product(callback_data.id, cb.from_user.id)
    if not p:
        return await cb.answer("Товар уже удалён", show_alert=True)
    card = (await wb.fetch_cards([p["nm"]])).get(p["nm"])
    if not card:
        return await cb.answer("WB не ответил, попробуйте позже", show_alert=True)
    await db.update_product_state(p["id"], card)
    await db.add_history(p["nm"], monitor.utc_iso(), card.price, card.qty, "bot")
    await cb.answer("Обновлено")
    p = await db.get_product(p["id"], cb.from_user.id)
    await cb.message.edit_text(await reports.card_text(p), reply_markup=kb.product_kb(p), disable_web_page_preview=True)


@router.callback_query(kb.ProdCB.filter(F.action == "chart"))
async def chart(cb: CallbackQuery, callback_data: kb.ProdCB):
    p = await db.get_product(callback_data.id, cb.from_user.id)
    if not p:
        return await cb.answer("Товар уже удалён", show_alert=True)
    await cb.answer("Рисую график…")
    png = await reports.chart_png(p)
    await cb.message.answer_photo(BufferedInputFile(png, filename=f"price_{p['nm']}.png"),
                                  caption=f"📈 {escape(short(p['name'], 60))}")


@router.callback_query(kb.ProdCB.filter(F.action == "add_rival"))
async def add_rival(cb: CallbackQuery, callback_data: kb.ProdCB, state: FSMContext):
    p = await db.get_product(callback_data.id, cb.from_user.id)
    if not p:
        return await cb.answer("Товар уже удалён", show_alert=True)
    await cb.answer()
    await state.set_state(Add.links)
    await state.update_data(parent=p["id"])
    await cb.message.answer(f"Пришлите ссылки или артикулы конкурентов для «{escape(short(p['name'], 40))}».")


@router.callback_query(kb.ProdCB.filter(F.action == "delete"))
async def delete(cb: CallbackQuery, callback_data: kb.ProdCB):
    p = await db.get_product(callback_data.id, cb.from_user.id)
    if not p:
        return await cb.answer("Товар уже удалён", show_alert=True)
    await cb.answer()
    await cb.message.edit_text(f"Перестать отслеживать «{escape(short(p['name'], 50))}»?",
                               reply_markup=kb.confirm_delete_kb(p["id"]))


@router.callback_query(kb.ProdCB.filter(F.action == "confirm_delete"))
async def confirm_delete(cb: CallbackQuery, callback_data: kb.ProdCB):
    await db.delete_product(callback_data.id, cb.from_user.id)
    await cb.answer("Удалено")
    await _show_list(cb.message, cb.from_user.id, edit=True)


# ---------- Сводка, Excel, настройки ----------

@router.message(StateFilter(None), F.text == kb.MENU_REPORT)
async def report(message: Message):
    await message.answer(await reports.daily_report(message.from_user.id), disable_web_page_preview=True)


@router.message(StateFilter(None), F.text == kb.MENU_EXCEL)
async def excel(message: Message):
    if not await db.count_products(message.from_user.id):
        return await message.answer("Пока нечего выгружать — добавьте товары.")
    async with ChatActionSender.upload_document(bot=message.bot, chat_id=message.chat.id):
        data = await reports.excel(message.from_user.id)
    await message.answer_document(BufferedInputFile(data, filename=f"wb_prices_{now():%Y-%m-%d}.xlsx"),
                                  caption="📥 Цены, остатки и история. Строки, где конкурент дешевле вас, подсвечены.")


def _settings_text() -> str:
    return "⚙️ <b>Настройки уведомлений</b>\nНажмите на пункт, чтобы переключить значение."


@router.message(StateFilter(None), F.text == kb.MENU_SETTINGS)
async def settings(message: Message):
    await message.answer(_settings_text(), reply_markup=kb.settings_kb(await db.get_user(message.from_user.id)))


@router.callback_query(kb.SetCB.filter())
async def settings_toggle(cb: CallbackQuery, callback_data: kb.SetCB):
    user = await db.get_user(cb.from_user.id)
    if callback_data.key == "price":
        await db.set_user(cb.from_user.id, price_pct=_cycle(config.PRICE_THRESHOLDS, user["price_pct"]))
    elif callback_data.key == "report":
        await db.set_user(cb.from_user.id, report_hour=_cycle(config.REPORT_HOURS, user["report_hour"]))
    elif callback_data.key == "stock":
        await db.set_user(cb.from_user.id, stock_low=_cycle(config.STOCK_LOW_LEVELS, user["stock_low"]))
    await cb.answer("Сохранено")
    await cb.message.edit_text(_settings_text(), reply_markup=kb.settings_kb(await db.get_user(cb.from_user.id)))


MENU_ACTIONS.update({kb.MENU_LIST: list_products, kb.MENU_REPORT: report, kb.MENU_EXCEL: excel,
                     kb.MENU_SETTINGS: settings, kb.MENU_ADD: None})


@router.message(StateFilter(None))
async def fallback(message: Message):
    await message.answer("Пришлите ссылку на товар WB или артикул — или выберите действие в меню 👇",
                         reply_markup=kb.main_menu())
