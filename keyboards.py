from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import rub, short

MENU_ADD = "➕ Добавить товар"
MENU_LIST = "📋 Мои товары"
MENU_REPORT = "📊 Сводка"
MENU_EXCEL = "📥 Excel"
MENU_SETTINGS = "⚙️ Настройки"


class RoleCB(CallbackData, prefix="role"):
    role: str      # mine / rival


class PickCB(CallbackData, prefix="pick"):
    action: str    # toggle / done / each / none / next / cancel
    id: int = 0    # для toggle — id моего товара


class ProdCB(CallbackData, prefix="p"):
    action: str    # view / chart / refresh / delete / confirm_delete / add_rival / links
    id: int


class ListCB(CallbackData, prefix="list"):
    action: str    # show / check_all


class SetCB(CallbackData, prefix="set"):
    key: str       # price / report / stock


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=MENU_ADD), KeyboardButton(text=MENU_LIST)],
        [KeyboardButton(text=MENU_REPORT), KeyboardButton(text=MENU_EXCEL), KeyboardButton(text=MENU_SETTINGS)],
    ], resize_keyboard=True, input_field_placeholder="Пришлите ссылку на товар WB или артикул")


def role_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Это мои товары", callback_data=RoleCB(role="mine"))
    b.button(text="🎯 Это конкуренты", callback_data=RoleCB(role="rival"))
    b.adjust(1)
    return b.as_markup()


def pick_kb(mines, selected: set[int], mode: str, last: bool = True, can_each: bool = False) -> InlineKeyboardMarkup:
    """Галочки «к каким моим товарам привязать». mode: batch — всем сразу, each — по одному, edit — правка связей."""
    b = InlineKeyboardBuilder()
    for m in mines:
        mark = "☑️" if m["id"] in selected else "⬜"
        b.row(InlineKeyboardButton(text=f"{mark} {short(m['name'], 30)} — {rub(m['price'])}",
                                   callback_data=PickCB(action="toggle", id=m["id"]).pack()))
    if mode == "batch":
        if selected:
            b.row(InlineKeyboardButton(text="✅ Привязать всех к отмеченным", callback_data=PickCB(action="done").pack()))
        if can_each:
            b.row(InlineKeyboardButton(text="🧩 По-разному для каждого", callback_data=PickCB(action="each").pack()))
        b.row(InlineKeyboardButton(text="Без привязки", callback_data=PickCB(action="none").pack()))
    elif mode == "each":
        b.row(InlineKeyboardButton(text="✅ Готово" if last else "Далее ➡️", callback_data=PickCB(action="next").pack()))
    else:
        b.row(InlineKeyboardButton(text="✅ Сохранить", callback_data=PickCB(action="done").pack()),
              InlineKeyboardButton(text="« Назад", callback_data=PickCB(action="cancel").pack()))
    return b.as_markup()


def list_kb(products, links: list[tuple[int, int]]) -> InlineKeyboardMarkup:
    """Мои товары, под каждым — его конкуренты (один конкурент может быть под несколькими); затем без привязки."""
    by_id = {p["id"]: p for p in products}
    linked = {r for r, _ in links}
    b = InlineKeyboardBuilder()
    mine = [p for p in products if p["role"] == "mine"]
    for m in mine:
        b.row(InlineKeyboardButton(text=f"⭐ {short(m['name'], 30)} — {rub(m['price'])}",
                                   callback_data=ProdCB(action="view", id=m["id"]).pack()))
        for r in [by_id[r_id] for r_id, m_id in links if m_id == m["id"] and r_id in by_id]:
            mark = " ❗" if r["price"] and m["price"] and r["price"] < m["price"] else ""
            b.row(InlineKeyboardButton(text=f"   ↳ 🎯 {short(r['name'], 26)} — {rub(r['price'])}{mark}",
                                       callback_data=ProdCB(action="view", id=r["id"]).pack()))
    for r in [p for p in products if p["role"] == "rival" and p["id"] not in linked]:
        b.row(InlineKeyboardButton(text=f"🎯 {short(r['name'], 30)} — {rub(r['price'])}",
                                   callback_data=ProdCB(action="view", id=r["id"]).pack()))
    b.row(InlineKeyboardButton(text="🔄 Проверить все сейчас", callback_data=ListCB(action="check_all").pack()))
    return b.as_markup()


def product_kb(p) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📈 График", callback_data=ProdCB(action="chart", id=p["id"]))
    b.button(text="🔄 Обновить", callback_data=ProdCB(action="refresh", id=p["id"]))
    if p["role"] == "mine":
        b.button(text="➕ Конкурент", callback_data=ProdCB(action="add_rival", id=p["id"]))
    else:
        b.button(text="🔗 Привязка", callback_data=ProdCB(action="links", id=p["id"]))
    b.button(text="🗑 Удалить", callback_data=ProdCB(action="delete", id=p["id"]))
    b.button(text="« К списку", callback_data=ListCB(action="show"))
    b.adjust(2, 2, 1)
    return b.as_markup()


def confirm_delete_kb(product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Да, удалить", callback_data=ProdCB(action="confirm_delete", id=product_id))
    b.button(text="Нет", callback_data=ProdCB(action="view", id=product_id))
    return b.as_markup()


def settings_kb(user) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    pct = user["price_pct"]
    b.button(text=f"Уведомлять о цене: {'любое изменение' if pct == 0 else f'от {pct}%'}", callback_data=SetCB(key="price"))
    hour = user["report_hour"]
    b.button(text=f"Сводка: {'выключена' if hour is None else f'каждый день в {hour}:00'}", callback_data=SetCB(key="report"))
    b.button(text=f"«Заканчивается»: меньше {user['stock_low']} шт", callback_data=SetCB(key="stock"))
    b.adjust(1)
    return b.as_markup()
