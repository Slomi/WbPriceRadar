import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { AVATAR } from "./config";
import { Item, Press, Span, Toast } from "./timeline";

const C = {
  bg: "#0e1621",
  header: "#17212b",
  inBubble: "#182533",
  outBubble: "#2b5278",
  text: "#f5f5f5",
  muted: "#7f91a4",
  accent: "#6ab3f3",
  button: "rgba(255,255,255,0.09)",
  pressed: "rgba(106,179,243,0.45)",
  input: "#17212b",
};

const clampOpts = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

type Props = {
  emptyHint?: string;
  title: string;
  label: string;
  items: Item[];
  typing: Span[];
  inputs: (Span & { text: string })[];
  replyKb: { at: number; rows: string[][] | null }[];
  presses: Press[];
  toasts?: Toast[];
  width: number;
  height: number;
};

const isPressed = (presses: Press[], frame: number, msgId: number | null, button: string) =>
  presses.some((p) => p.msgId === msgId && p.button === button && frame >= p.at && frame < p.at + 14);

const Button: React.FC<{ text: string; pressed: boolean; flex?: boolean }> = ({ text, pressed, flex }) => (
  <div
    style={{
      flex: flex ? 1 : undefined,
      background: pressed ? C.pressed : C.button,
      borderRadius: 10,
      padding: "10px 12px",
      fontSize: 21,
      color: C.text,
      textAlign: "center",
      scale: pressed ? "0.96" : "1",
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis",
    }}
  >
    {text}
  </div>
);

export const ChatPanel: React.FC<Props> = ({ emptyHint, title, label, items, typing, inputs, replyKb, presses, toasts = [], width, height }) => {
  const frame = useCurrentFrame();
  const visible = items.filter((i) => i.start <= frame);
  const isTyping = typing.some((s) => frame >= s.from && frame < s.to);
  const input = inputs.find((s) => frame >= s.from && frame < s.to);
  const typed = input
    ? input.text.slice(0, Math.ceil((input.text.length * (frame - input.from + 1)) / (input.to - input.from)))
    : "";
  const kb = [...replyKb].reverse().find((k) => k.at <= frame)?.rows ?? null;
  const toast = toasts.find((x) => frame >= x.at && frame < x.at + 40);

  return (
    <div style={{ width, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ fontSize: 26, color: C.muted, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase" }}>
        {label}
      </div>
      <div
        style={{
          width,
          height,
          background: C.bg,
          borderRadius: 22,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {toast ? (
          <div
            style={{
              position: "absolute", top: 110, left: "50%", zIndex: 5, translate: "-50% 0px",
              background: "rgba(20,30,40,0.95)", color: "#fff", fontSize: 22, padding: "12px 24px", borderRadius: 14,
              boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
              opacity: interpolate(frame - toast.at, [0, 6, 32, 40], [0, 1, 1, 0], clampOpts),
            }}
          >
            {toast.text}
          </div>
        ) : null}
        {/* Шапка */}
        <div style={{ background: C.header, padding: "16px 22px", display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 54, height: 54, borderRadius: 27, background: AVATAR.gradient,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, fontWeight: 700, color: "#fff",
            }}
          >
            {AVATAR.letter}
          </div>
          <div>
            <div style={{ fontSize: 25, fontWeight: 600, color: C.text }}>{title}</div>
            <div style={{ fontSize: 19, color: isTyping ? C.accent : C.muted }}>{isTyping ? "печатает…" : "бот"}</div>
          </div>
        </div>

        {/* Лента сообщений: новые снизу, старые уезжают вверх */}
        <div
          style={{
            flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "flex-end",
            padding: "0 18px 12px", gap: 10,
          }}
        >
          {visible.length === 0 && emptyHint ? (
            <div style={{ margin: "auto", fontSize: 24, color: C.muted, textAlign: "center", maxWidth: 460 }}>{emptyHint}</div>
          ) : null}
          {visible.map((item) => {
            const age = frame - item.start;
            const edit = [...item.edits].reverse().find((e) => e.at <= frame);
            const html = edit ? edit.text : item.text;
            const inline = edit ? edit.inline : item.inline;
            const flash = edit ? interpolate(frame - edit.at, [0, 12], [0.35, 0], clampOpts) : 0;
            // очень длинные сообщения (заявка с перепиской) показываем с начала, хвост плавно гаснет
            const long = html.replace(/<[^>]+>/g, "").length > 420;
            return (
              <div
                key={`${item.chat}-${item.id}`}
                style={{
                  maxHeight: interpolate(age, [0, 10], [0, 1400], { ...clampOpts, easing: Easing.bezier(0.2, 0.8, 0.2, 1) }),
                  opacity: interpolate(age, [0, 8], [0, 1], clampOpts),
                  translate: interpolate(age, [0, 10], ["0px 18px", "0px 0px"], clampOpts),
                  alignSelf: item.out ? "flex-end" : "flex-start",
                  maxWidth: "86%",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    background: item.out ? C.outBubble : C.inBubble,
                    boxShadow: flash ? `0 0 0 3px rgba(106,179,243,${flash})` : undefined,
                    borderRadius: 16,
                    borderBottomRightRadius: item.out ? 4 : 16,
                    borderBottomLeftRadius: item.out ? 16 : 4,
                    padding: "11px 15px",
                    fontSize: 22,
                    lineHeight: 1.38,
                    color: C.text,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    maxHeight: long ? 470 : undefined,
                    overflow: "hidden",
                    maskImage: long ? "linear-gradient(black 78%, transparent)" : undefined,
                  }}
                >
                  {item.replyTo ? (
                    <div
                      style={{
                        borderLeft: `3px solid ${C.accent}`, paddingLeft: 10, marginBottom: 6, fontSize: 18,
                        color: C.accent, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                      }}
                    >
                      {item.replyTo}
                    </div>
                  ) : null}
                  {item.kind === "photo" && item.file ? (
                    <Img src={staticFile(`media/${item.file}`)}
                         style={{ display: "block", width: "100%", maxHeight: 300, objectFit: "contain", borderRadius: 10,
                                  marginBottom: html ? 8 : 0, background: "#fff" }} />
                  ) : null}
                  {item.kind === "document" && item.file ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: html ? 8 : 0 }}>
                      <div style={{ width: 52, height: 52, borderRadius: 26, background: C.accent, display: "flex",
                                    alignItems: "center", justifyContent: "center", fontSize: 26 }}>📄</div>
                      <div style={{ fontSize: 21, fontWeight: 600 }}>{item.file.replace(/^\d+_/, "")}</div>
                    </div>
                  ) : null}
                  <span className="tg" dangerouslySetInnerHTML={{ __html: html }} />
                </div>
                {inline?.map((row, r) => (
                  <div key={r} style={{ display: "flex", gap: 6 }}>
                    {row.map((b) => (
                      <Button key={b} text={b} flex pressed={isPressed(presses, frame, item.id, b)} />
                    ))}
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        {/* Reply-клавиатура */}
        {kb ? (
          <div style={{ background: C.header, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
            {kb.map((row, r) => (
              <div key={r} style={{ display: "flex", gap: 6 }}>
                {row.map((b) => (
                  <Button key={b} text={b} flex pressed={isPressed(presses, frame, null, b)} />
                ))}
              </div>
            ))}
          </div>
        ) : null}

        {/* Поле ввода */}
        <div
          style={{
            background: C.input, borderTop: "1px solid rgba(255,255,255,0.05)", padding: "16px 22px",
            fontSize: 22, color: typed ? C.text : C.muted, display: "flex", alignItems: "center", gap: 12, minHeight: 34,
          }}
        >
          <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {typed || "Сообщение"}
            {typed ? <span style={{ opacity: Math.floor(frame / 8) % 2 ? 0 : 1, color: C.accent }}>|</span> : null}
          </span>
          <span style={{ fontSize: 26, color: typed ? C.accent : C.muted }}>➤</span>
        </div>
      </div>
    </div>
  );
};
