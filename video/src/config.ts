// Всё, что относится к конкретному боту. Остальной код ролика общий — его обычно не трогают.
export type Ev = {
  op: string; // user / bot / edit / edit_markup / click / toast / clock / photo / document
  chat: number | null;
  id?: number;
  text?: string;
  button?: string;
};

export const BOT_TITLE = "WB Радар — мониторинг цен";
export const AVATAR = { letter: "W", gradient: "linear-gradient(135deg,#cb11ab,#7a1ad1)" };
export const INTRO = { title: "Мониторинг цен конкурентов на WB", subtitle: "Telegram-бот для селлеров · уведомления · графики · Excel" };
export const OUTRO = {
  title: "Что умеет бот",
  features: [
    "Мои товары и конкуренты — по ссылке или артикулу",
    "Конкурент подешевел или стал дешевле вас — сразу пишет",
    "Остатки: закончился, снова в наличии, заканчивается",
    "График истории цен: вы и конкуренты",
    "Утренняя сводка и выгрузка в Excel",
  ],
  footer: "Ролик собран из реальных ответов бота и цен WB · для демо уведомления прошлая цена конкурента изменена",
};

export const EMPTY_HINTS: (string | undefined)[] = [undefined];
export const MEDIA_PANEL = { label: "Графики и файлы", hint: "Здесь появятся графики и выгрузки, которые присылает бот" };

export const CAPTION_RULES = (_chats: number[]): { test: (e: Ev) => boolean; text: string }[] => [
  { test: (e) => e.op === "user" && e.text === "/start", text: "Селлер подключает мониторинг" },
  { test: (e) => e.op === "user" && !!e.text?.includes("wildberries.ru"), text: "Добавляет свои товары по ссылке" },
  { test: (e) => e.op === "click" && !!e.button?.startsWith("🎯"), text: "Конкуренты — пачкой, с привязкой к своим товарам" },
  { test: (e) => e.op === "click" && !!e.button?.startsWith("🧩"), text: "Один конкурент — к одному или нескольким вашим" },
  { test: (e) => e.op === "user" && !!e.text?.includes("Мои товары"), text: "❗ — конкурент дешевле вас" },
  { test: (e) => e.op === "photo", text: "История цен: вы и конкуренты на одном графике" },
  { test: (e) => e.op === "clock", text: "Конкурент подешевел — бот сразу пишет" },
  { test: (e) => e.op === "user" && !!e.text?.includes("Сводка"), text: "Сводка: ваше место по цене" },
  { test: (e) => e.op === "document", text: "Всё в Excel — с историей и подсветкой" },
];
