import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# Кому разрешено пользоваться ботом (через запятую). Пусто — всем: удобно для демо.
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_IDS", "").replace(" ", "").split(",") if x}
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
DB_PATH = os.getenv("DB_PATH", "monitor.db")
PROXY = os.getenv("PROXY", "").strip()

CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "60"))  # как часто проверять цены
WB_DEST = os.getenv("WB_DEST", "-1257786")  # регион доставки для цен и остатков (Москва)
MAX_PRODUCTS_PER_USER = 50

# Значения настроек, между которыми переключается кнопка
PRICE_THRESHOLDS = [0, 3, 5, 10]          # % изменения цены для уведомления (0 — любое)
REPORT_HOURS = [8, 9, 10, 12, 18, None]   # час ежедневного отчёта (None — выключен)
STOCK_LOW_LEVELS = [5, 10, 20, 50]        # «заканчивается», шт
