import React, { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import { ChatPanel } from "./ChatPanel";
import { MediaPanel } from "./MediaPanel";
import { BOT_TITLE, EMPTY_HINTS, INTRO as INTRO_TEXT, MEDIA_PANEL, OUTRO as OUTRO_TEXT } from "./config";
import { CHATS, INTRO, OUTRO, buildTimeline } from "./timeline";

const { fontFamily } = loadFont("normal", { weights: ["400", "600", "700"], subsets: ["latin", "cyrillic"] });
const FONT = `${fontFamily}, "Segoe UI Emoji", "Apple Color Emoji", sans-serif`;
const clampOpts = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const DemoVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const tl = useMemo(() => buildTimeline(), []);
  const caption = [...tl.captions].reverse().find((c) => c.at <= frame);
  const clock = tl.clocks.find((c) => frame >= c.from && frame < c.to);
  const outroStart = durationInFrames - OUTRO;
  const panelW = 800;
  const panelH = 830;
  const single = CHATS.length === 1; // одно окно чата + панель медиа справа

  const sceneOpacity = interpolate(frame, [INTRO - 12, INTRO, outroStart - 6, outroStart + 10], [0, 1, 1, 0], clampOpts);

  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 30% 0%, #1d2b3a 0%, #0b121a 70%)", fontFamily: FONT }}>
      <style>{`.tg a{color:#6ab3f3;text-decoration:none}.tg b{font-weight:700}.tg i{color:#9fb2c4}.tg code{font-family:Consolas,monospace;color:#8fd3ff}`}</style>

      {/* Вступление */}
      <AbsoluteFill
        style={{
          justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 26,
          opacity: interpolate(frame, [0, 12, INTRO - 14, INTRO], [0, 1, 1, 0], clampOpts),
        }}
      >
        <div style={{ fontSize: 96, fontWeight: 700, color: "#fff", translate: interpolate(frame, [0, 20], ["0px 30px", "0px 0px"], { ...clampOpts, easing: Easing.bezier(0.16, 1, 0.3, 1) }) }}>
          {INTRO_TEXT.title}
        </div>
        <div style={{ fontSize: 44, color: "#8fa6bd" }}>{INTRO_TEXT.subtitle}</div>
      </AbsoluteFill>

      {/* Основная сцена */}
      <AbsoluteFill style={{ opacity: sceneOpacity, padding: "56px 110px 40px", flexDirection: "column", gap: 26 }}>
        <div style={{ height: 70, display: "flex", alignItems: "center" }}>
          {caption ? (
            <div
              key={caption.at}
              style={{
                fontSize: 52, fontWeight: 700, color: "#fff",
                opacity: interpolate(frame - caption.at, [0, 10], [0, 1], clampOpts),
                translate: interpolate(frame - caption.at, [0, 12], ["0px 16px", "0px 0px"], { ...clampOpts, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
              }}
            >
              {caption.text}
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          {CHATS.map((chat, i) => (
            <ChatPanel
              key={chat.id}
              emptyHint={EMPTY_HINTS[i]}
              title={BOT_TITLE}
              label={chat.label}
              items={tl.items.filter((it) => it.chat === chat.id)}
              typing={tl.typing[chat.id]}
              inputs={tl.inputs[chat.id]}
              replyKb={tl.replyKb[chat.id]}
              presses={tl.presses[chat.id]}
              toasts={tl.toasts[chat.id]}
              width={panelW}
              height={panelH}
            />
          ))}
          {single ? (
            <MediaPanel media={tl.media} captions={tl.captions} label={MEDIA_PANEL.label} hint={MEDIA_PANEL.hint} width={panelW} height={panelH} />
          ) : null}
        </div>
      </AbsoluteFill>

      {/* Заставка «прошло время» */}
      {clock ? (
        <AbsoluteFill
          style={{
            justifyContent: "center", alignItems: "center", background: "rgba(8,12,18,0.82)",
            opacity: interpolate(frame - clock.from, [0, 8, clock.to - clock.from - 8, clock.to - clock.from], [0, 1, 1, 0], clampOpts),
          }}
        >
          <div style={{ fontSize: 40, color: "#8fa6bd", marginBottom: 12 }}>⏳ прошло время</div>
          <div style={{ fontSize: 76, fontWeight: 700, color: "#fff" }}>{clock.text}</div>
        </AbsoluteFill>
      ) : null}

      {/* Финал */}
      <AbsoluteFill
        style={{
          justifyContent: "center", paddingLeft: 220, flexDirection: "column", gap: 22,
          opacity: interpolate(frame, [outroStart + 4, outroStart + 18], [0, 1], clampOpts),
        }}
      >
        <div style={{ fontSize: 72, fontWeight: 700, color: "#fff", marginBottom: 20 }}>{OUTRO_TEXT.title}</div>
        {OUTRO_TEXT.features.map((f, i) => (
          <div
            key={f}
            style={{
              fontSize: 44, color: "#dbe6f0",
              opacity: interpolate(frame, [outroStart + 14 + i * 6, outroStart + 24 + i * 6], [0, 1], clampOpts),
              translate: interpolate(frame, [outroStart + 14 + i * 6, outroStart + 26 + i * 6], ["-24px 0px", "0px 0px"], { ...clampOpts, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
            }}
          >
            <span style={{ color: "#6ab3f3" }}>✓</span> {f}
          </div>
        ))}
        <div style={{ fontSize: 30, color: "#7f91a4", marginTop: 30 }}>{OUTRO_TEXT.footer}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
