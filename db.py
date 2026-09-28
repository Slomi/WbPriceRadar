import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    price_pct      INTEGER NOT NULL DEFAULT 0,    -- порог изменения цены для уведомления, %
    report_hour    INTEGER DEFAULT 9,             -- NULL — отчёт выключен
    stock_low      INTEGER NOT NULL DEFAULT 10,
    last_report    TEXT                           -- дата последнего отчёта (локальная)
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    nm          INTEGER NOT NULL,
    name        TEXT, brand TEXT, supplier TEXT,
    role        TEXT NOT NULL,                    -- mine / rival
    parent_id   INTEGER,                          -- устарело: связи теперь в таблице links
    price       REAL, basic REAL, qty INTEGER, rating REAL, feedbacks INTEGER,
    checked_at  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE (user_id, nm)
);
CREATE TABLE IF NOT EXISTS links (               -- конкурент ↔ мой товар, многие-ко-многим
    rival_id  INTEGER NOT NULL,
    mine_id   INTEGER NOT NULL,
    PRIMARY KEY (rival_id, mine_id)
);
CREATE TABLE IF NOT EXISTS history (             -- общая для всех пользователей: один артикул — одна история
    nm      INTEGER NOT NULL,
    ts      TEXT NOT NULL,                        -- UTC ISO
    price   REAL,
    qty     INTEGER,
    source  TEXT NOT NULL,                        -- wb (недельная история сайта) / bot (наши проверки)
    PRIMARY KEY (nm, ts, source)
);
"""


def _connect():
    return aiosqlite.connect(config.DB_PATH)


async def _fetch(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(sql, params) as cur:
            return list(await cur.fetchall())


async def _exec(sql: str, params: tuple = ()) -> int:
    async with _connect() as conn:
        cur = await conn.execute(sql, params)
        await conn.commit()
        return cur.lastrowid


async def init() -> None:
    async with _connect() as conn:
        await conn.executescript(SCHEMA)
        # миграция со старой схемы «один конкурент — один мой товар»
        await conn.execute("INSERT OR IGNORE INTO links (rival_id, mine_id) "
                           "SELECT id, parent_id FROM products WHERE parent_id IS NOT NULL")
        await conn.execute("UPDATE products SET parent_id=NULL WHERE parent_id IS NOT NULL")
        await conn.commit()


# --- пользователи ---

async def get_user(user_id: int) -> aiosqlite.Row:
    await _exec("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    return (await _fetch("SELECT * FROM users WHERE user_id=?", (user_id,)))[0]


async def set_user(user_id: int, **fields) -> None:
    await get_user(user_id)
    cols = ", ".join(f"{k}=?" for k in fields)
    await _exec(f"UPDATE users SET {cols} WHERE user_id=?", (*fields.values(), user_id))


async def users_with_products() -> list[aiosqlite.Row]:
    return await _fetch("SELECT u.* FROM users u WHERE EXISTS (SELECT 1 FROM products p WHERE p.user_id=u.user_id)")


# --- товары ---

async def add_product(user_id: int, card, role: str) -> int | None:
    """None — такой артикул у пользователя уже есть."""
    try:
        return await _exec(
            "INSERT INTO products (user_id, nm, name, brand, supplier, role, price, basic, qty, rating, "
            "feedbacks, checked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (user_id, card.nm, card.name, card.brand, card.supplier, role, card.price, card.basic,
             card.qty, card.rating, card.feedbacks))
    except aiosqlite.IntegrityError:
        return None


async def get_by_nm(user_id: int, nm: int) -> aiosqlite.Row | None:
    rows = await _fetch("SELECT * FROM products WHERE user_id=? AND nm=?", (user_id, nm))
    return rows[0] if rows else None


async def get_product(product_id: int, user_id: int) -> aiosqlite.Row | None:
    rows = await _fetch("SELECT * FROM products WHERE id=? AND user_id=?", (product_id, user_id))
    return rows[0] if rows else None


async def user_products(user_id: int) -> list[aiosqlite.Row]:
    return await _fetch("SELECT * FROM products WHERE user_id=? ORDER BY id", (user_id,))


async def count_products(user_id: int) -> int:
    return (await _fetch("SELECT COUNT(*) AS n FROM products WHERE user_id=?", (user_id,)))[0]["n"]


async def rivals_of(mine_id: int) -> list[aiosqlite.Row]:
    return await _fetch("SELECT p.* FROM products p JOIN links l ON l.rival_id=p.id WHERE l.mine_id=? "
                        "ORDER BY p.price IS NULL, p.price", (mine_id,))


async def mines_of(rival_id: int) -> list[aiosqlite.Row]:
    return await _fetch("SELECT p.* FROM products p JOIN links l ON l.mine_id=p.id WHERE l.rival_id=? ORDER BY p.id",
                        (rival_id,))


async def all_links(user_id: int) -> list[tuple[int, int]]:
    rows = await _fetch("SELECT l.rival_id, l.mine_id FROM links l JOIN products p ON p.id=l.rival_id "
                        "WHERE p.user_id=?", (user_id,))
    return [(r["rival_id"], r["mine_id"]) for r in rows]


async def set_links(rival_id: int, mine_ids: list[int]) -> None:
    async with _connect() as conn:
        await conn.execute("DELETE FROM links WHERE rival_id=?", (rival_id,))
        await conn.executemany("INSERT OR IGNORE INTO links (rival_id, mine_id) VALUES (?, ?)",
                               [(rival_id, m) for m in mine_ids])
        await conn.commit()


async def add_links(rival_id: int, mine_ids: list[int]) -> None:
    async with _connect() as conn:
        await conn.executemany("INSERT OR IGNORE INTO links (rival_id, mine_id) VALUES (?, ?)",
                               [(rival_id, m) for m in mine_ids])
        await conn.commit()


async def delete_product(product_id: int, user_id: int) -> None:
    if await get_product(product_id, user_id):
        await _exec("DELETE FROM links WHERE rival_id=? OR mine_id=?", (product_id, product_id))
        await _exec("DELETE FROM products WHERE id=? AND user_id=?", (product_id, user_id))


async def all_nms() -> list[int]:
    return [r["nm"] for r in await _fetch("SELECT DISTINCT nm FROM products")]


async def products_by_nm(nm: int) -> list[aiosqlite.Row]:
    return await _fetch("SELECT * FROM products WHERE nm=?", (nm,))


async def update_product_state(product_id: int, card) -> None:
    await _exec("UPDATE products SET name=?, price=?, basic=?, qty=?, rating=?, feedbacks=?, checked_at=datetime('now') "
                "WHERE id=?", (card.name, card.price, card.basic, card.qty, card.rating, card.feedbacks, product_id))


# --- история ---

async def add_history(nm: int, ts_iso: str, price: float | None, qty: int | None, source: str) -> None:
    await _exec("INSERT OR IGNORE INTO history (nm, ts, price, qty, source) VALUES (?, ?, ?, ?, ?)",
                (nm, ts_iso, price, qty, source))


async def has_wb_history(nm: int) -> bool:
    return bool(await _fetch("SELECT 1 FROM history WHERE nm=? AND source='wb' LIMIT 1", (nm,)))


async def history(nm: int, since_iso: str | None = None) -> list[aiosqlite.Row]:
    if since_iso:
        return await _fetch("SELECT * FROM history WHERE nm=? AND ts>=? ORDER BY ts", (nm, since_iso))
    return await _fetch("SELECT * FROM history WHERE nm=? ORDER BY ts", (nm,))


async def price_between(nm: int, from_iso: str, to_iso: str) -> float | None:
    """Последняя известная цена в окне [from, to] — чтобы «за сутки» не сравнивать с точкой месячной давности."""
    rows = await _fetch("SELECT price FROM history WHERE nm=? AND ts>=? AND ts<=? AND price IS NOT NULL "
                        "ORDER BY ts DESC LIMIT 1", (nm, from_iso, to_iso))
    return rows[0]["price"] if rows else None
