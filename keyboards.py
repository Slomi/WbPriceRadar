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
    parent: int    # 0 — без привязки


class ProdCB(CallbackData, prefix="p"):
    action: str    # view / chart / refresh / delete / confirm_delete / add_rival
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


def role_kb(mine_products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Это мои товары", callback_data=RoleCB(role="mine", parent=0))
    for m in mine_products[:8]:
        b.button(text=f"🎯 Конкуренты для «{short(m['name'], 28)}»", callback_data=RoleCB(role="rival", parent=m["id"]))
    b.button(text="🎯 Конкуренты (без привязки)", callback_data=RoleCB(role="rival", parent=0))
    b.adjust(1)
    return b.as_markup()


def list_kb(products) -> InlineKeyboardMarkup:
    """Мои товары, под каждым — его конкуренты; затем конкуренты без привязки."""
    b = InlineKeyboardBuilder()
    mine = [p for p in products if p["role"] == "mine"]
    for m in mine:
        b.row(InlineKeyboardButton(text=f"⭐ {short(m['name'], 30)} — {rub(m['price'])}",
                                   callback_data=ProdCB(action="view", id=m["id"]).pack()))
        for r in [p for p in products if p["parent_id"] == m["id"]]:
            mark = " ❗" if r["price"] and m["price"] and r["price"] < m["price"] else ""
            b.row(InlineKeyboardButton(text=f"   ↳ 🎯 {short(r['name'], 26)} — {rub(r['price'])}{mark}",
                                       callback_data=ProdCB(action="view", id=r["id"]).pack()))
    for r in [p for p in products if p["role"] == "rival" and not p["parent_id"]]:
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
    b.button(text="🗑 Удалить", callback_data=ProdCB(action="delete", id=p["id"]))
    b.button(text="« К списку", callback_data=ListCB(action="show"))
    b.adjust(2, 2, 1) if p["role"] == "mine" else b.adjust(2, 1, 1)
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
