// Превращает запись реального диалога с ботом (data/script.json от tg_mock.py) в раскадровку.
// Тайминги считаются из длины текстов — менять руками обычно не нужно.
import script from "./data/script.json";
import { CAPTION_RULES, Ev as ConfigEv } from "./config";

export const FPS = 30;
export const INTRO = 3 * FPS;
export const OUTRO = 5 * FPS;

type Markup = { inline?: string[][]; reply?: string[][]; remove?: boolean } | null;
export type Preview = { sheet: string; rows: string[][] } | null;
type Ev = ConfigEv & { markup?: Markup; reply_to?: number | null; file?: string; preview?: Preview };

export type Edit = { at: number; text: string; inline?: string[][] };
export type Item = {
  id: number;
  chat: number;
  out: boolean; // сообщение пользователя (справа, синее)
  start: number;
  kind: "text" | "photo" | "document";
  text: string; // HTML
  file?: string; // для фото и документов: имя файла в public/media
  inline?: string[][];
  replyTo?: string;
  edits: Edit[];
};
export type Media = { at: number; kind: "photo" | "document"; file: string; caption: string; preview?: Preview };
export type Span = { from: number; to: number };
export type Press = { at: number; msgId: number | null; button: string }; // msgId=null — кнопка reply-клавиатуры
export type Caption = { at: number; text: string };
export type Toast = { at: number; text: string };
export type Clock = Span & { text: string };

export const CHATS: { id: number; label: string }[] = script.chats;

const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const plain = (s: string) => s.replace(/<[^>]+>/g, "");
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export type Timeline = {
  items: Item[];
  media: Media[]; // фото и документы — для боковой панели в режиме одного чата
  typing: Record<number, Span[]>; // «печатает…» в шапке чата
  inputs: Record<number, (Span & { text: string })[]>; // набор текста в поле ввода
  replyKb: Record<number, { at: number; rows: string[][] | null }[]>;
  presses: Record<number, Press[]>;
  toasts: Record<number, Toast[]>; // всплывашки после нажатия inline-кнопки
  clocks: Clock[]; // заставка «прошло время»
  captions: Caption[];
  duration: number;
};

const perChat = <T,>(): Record<number, T[]> => Object.fromEntries(CHATS.map((c) => [c.id, [] as T[]]));

export const buildTimeline = (): Timeline => {
  const events = script.events as Ev[];
  const rules = CAPTION_RULES(CHATS.map((c) => c.id));
  const tl: Timeline = {
    items: [], media: [], typing: perChat(), inputs: perChat(), replyKb: perChat(), presses: perChat(),
    toasts: perChat(), clocks: [], captions: [], duration: 0,
  };
  const byId = new Map<string, Item>();
  const usedCaptions = new Set<number>();
  let t = INTRO + 10;
  let lastUserChat = CHATS[0].id;

  events.forEach((e, idx) => {
    rules.forEach((r, i) => {
      if (!usedCaptions.has(i) && r.test(e)) {
        usedCaptions.add(i);
        tl.captions.push({ at: t, text: r.text });
      }
    });
    const next = events[idx + 1];

    if (e.op === "user" && e.chat !== null && e.text) {
      const chat = e.chat;
      const kbNow = [...tl.replyKb[chat]].reverse().find((k) => k.at <= t)?.rows ?? null;
      if (kbNow?.some((row) => row.includes(e.text!))) {
        tl.presses[chat].push({ at: t, msgId: null, button: e.text });
        t += 14;
      } else {
        const dur = clamp(Math.round(e.text.length * 1.1), 14, 70);
        tl.inputs[chat].push({ from: t, to: t + dur, text: e.text });
        t += dur + 4;
      }
      const replied = e.reply_to ? byId.get(`${chat}:${e.reply_to}`) : undefined;
      const item: Item = {
        id: e.id!, chat, out: true, start: t, kind: "text", text: escapeHtml(e.text), edits: [],
        replyTo: replied ? plain(replied.text).split("\n")[0] : undefined,
      };
      tl.items.push(item);
      byId.set(`${chat}:${e.id}`, item);
      lastUserChat = chat;
      t += 10;
    } else if (e.op === "click" && e.chat !== null) {
      tl.presses[e.chat].push({ at: t, msgId: e.id!, button: e.button! });
      lastUserChat = e.chat;
      t += 16;
    } else if (e.op === "toast" && e.text) {
      tl.toasts[lastUserChat].push({ at: t, text: e.text });
    } else if (e.op === "clock" && e.text) {
      t += 10;
      tl.clocks.push({ from: t, to: t + 50, text: e.text });
      t += 56;
    } else if ((e.op === "bot" || e.op === "photo" || e.op === "document") && e.chat !== null) {
      const chat = e.chat;
      const text = e.text ?? "";
      const len = plain(text).length;
      const isMedia = e.op !== "bot";
      if (chat === lastUserChat) {
        const typing = isMedia ? 24 : len > 140 ? 40 : 14;
        tl.typing[chat].push({ from: t, to: t + typing });
        t += typing;
      } else {
        t += 8; // уведомление в другой чат приходит почти сразу
      }
      const item: Item = {
        id: e.id!, chat, out: false, start: t, kind: isMedia ? (e.op as "photo" | "document") : "text",
        text, file: e.file, edits: [], inline: e.markup?.inline,
      };
      tl.items.push(item);
      byId.set(`${chat}:${e.id}`, item);
      if (isMedia && e.file) {
        tl.media.push({ at: t, kind: e.op as "photo" | "document", file: e.file, caption: text, preview: e.preview });
      }
      if (e.markup?.reply) tl.replyKb[chat].push({ at: t, rows: e.markup.reply });
      if (e.markup?.remove) tl.replyKb[chat].push({ at: t, rows: null });
      // пауза на чтение (на медиа — чтобы рассмотреть); если следом сразу ещё сообщение бота — короче
      const burst = next && (next.op === "bot" || next.op === "toast");
      t += isMedia ? 110 : burst ? 12 : clamp(Math.round(len * 0.55), 30, 135);
    } else if (e.op === "edit_markup" && e.chat !== null && !e.markup?.inline) {
      // бот просто убрал кнопки — паузу не тратим
      const item = byId.get(`${e.chat}:${e.id}`);
      if (item) item.edits.push({ at: t, text: [...item.edits].pop()?.text ?? item.text });
      t += 6;
    } else if ((e.op === "edit" || e.op === "edit_markup") && e.chat !== null) {
      const item = byId.get(`${e.chat}:${e.id}`);
      const last = item ? ([...item.edits].pop()?.text ?? item.text) : "";
      const text = e.op === "edit" ? e.text ?? "" : last;
      if (item) item.edits.push({ at: t, text, inline: e.markup?.inline });
      // если дальше клик — даём рассмотреть кнопки, иначе — прочитать текст
      const buttons = (e.markup?.inline ?? []).flat().length;
      const quick = next && next.op === "click";
      t += quick ? clamp(20 + buttons * 3, 30, 80) : clamp(Math.round(plain(text).length * 0.55), 60, 150);
    }
  });

  tl.duration = t + 45 + OUTRO; // короткая пауза на последней сцене перед финалом
  return tl;
};
