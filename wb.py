"""Публичные данные Wildberries: карточки товаров и недельная история цен.

WB отсекает запросы по TLS-отпечатку (aiohttp/httpx получают 400/403), поэтому ходим через
curl_cffi, который подключается как обычный Chrome.
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from curl_cffi.requests import AsyncSession

import config

CARD_URL = "https://card.wb.ru/cards/v4/detail"
NM_RE = re.compile(r"(?:wildberries\.ru/catalog/|wb\.ru/catalog/|^|\s)(\d{5,12})(?=/|\s|$|\?)")
BASKETS = range(1, 81)
_basket_by_vol: dict[int, int] = {}  # найденный CDN-сервер для «тома» артикулов


@dataclass
class Card:
    nm: int
    name: str
    brand: str
    supplier: str
    price: float | None   # цена продавца со скидкой, ₽ (None — нет в наличии)
    basic: float | None   # цена до скидки, ₽
    qty: int
    rating: float
    feedbacks: int

    @property
    def url(self) -> str:
        return f"https://www.wildberries.ru/catalog/{self.nm}/detail.aspx"

    @property
    def discount(self) -> int:
        return round((1 - self.price / self.basic) * 100) if self.price and self.basic else 0


def parse_nms(text: str) -> list[int]:
    """Артикулы из ссылок и чисел в тексте, без повторов, в порядке появления."""
    seen: list[int] = []
    for m in NM_RE.finditer(text.replace(",", " ")):
        nm = int(m.group(1))
        if nm not in seen:
            seen.append(nm)
    return seen


def _parse_card(p: dict) -> Card:
    priced = [s["price"] for s in p.get("sizes", []) if s.get("price")]
    best = min(priced, key=lambda x: x["product"]) if priced else None
    return Card(
        nm=p["id"],
        name=p.get("name", ""),
        brand=p.get("brand", ""),
        supplier=p.get("supplier", ""),
        price=best["product"] / 100 if best else None,
        basic=best["basic"] / 100 if best else None,
        qty=int(p.get("totalQuantity") or 0),
        rating=float(p.get("reviewRating") or p.get("rating") or 0),
        feedbacks=int(p.get("feedbacks") or 0),
    )


def _session() -> AsyncSession:
    return AsyncSession(impersonate="chrome", timeout=20, max_clients=16)


async def fetch_cards(nms: list[int]) -> dict[int, Card]:
    """Карточки пачками по 100 артикулов. Несуществующих артикулов в ответе просто нет."""
    result: dict[int, Card] = {}
    async with _session() as s:
        for i in range(0, len(nms), 100):
            chunk = nms[i:i + 100]
            url = f"{CARD_URL}?appType=1&curr=rub&dest={config.WB_DEST}&nm={';'.join(map(str, chunk))}"
            for attempt in range(3):
                try:
                    r = await s.get(url)
                    r.raise_for_status()
                    for p in r.json().get("products", []):
                        card = _parse_card(p)
                        result[card.nm] = card
                    break
                except Exception:
                    if attempt == 2:
                        logging.exception("WB: не удалось получить карточки %s", chunk)
                    await asyncio.sleep(2 * (attempt + 1))
    return result


async def _history_json(s: AsyncSession, basket: int, nm: int):
    vol, part = nm // 100000, nm // 1000
    url = f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm}/info/price-history.json"
    try:
        r = await s.get(url, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


async def fetch_price_history(nm: int) -> list[tuple[datetime, float]]:
    """Недельная история цены с сайта WB: [(дата UTC, цена ₽)]. Сервер ищем параллельно и запоминаем."""
    vol = nm // 100000
    async with _session() as s:
        data = await _history_json(s, _basket_by_vol[vol], nm) if vol in _basket_by_vol else None
        if data is None:
            results = await asyncio.gather(*(_history_json(s, b, nm) for b in BASKETS))
            for b, res in zip(BASKETS, results):
                if res is not None:
                    _basket_by_vol[vol], data = b, res
                    break
    if not isinstance(data, list):
        return []
    return [(datetime.fromtimestamp(x["dt"], timezone.utc), x["price"]["RUB"] / 100)
            for x in data if x.get("price", {}).get("RUB")]
