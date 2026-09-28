import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Caption, Media } from "./timeline";

const clampOpts = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Режим одного чата: крупно показывает последнее фото или файл, которые прислал бот
export const MediaPanel: React.FC<{
  media: Media[]; captions: Caption[]; label: string; hint: string; width: number; height: number;
}> = ({ media, captions, label, hint, width, height }) => {
  const frame = useCurrentFrame();
  const current = [...media].reverse().find((m) => m.at <= frame);
  const age = current ? frame - current.at : 0;
  const caption = current?.caption.replace(/<[^>]+>/g, "") ?? "";

  return (
    <div style={{ width, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ fontSize: 26, color: "#7f91a4", fontWeight: 600, letterSpacing: 1, textTransform: "uppercase" }}>
        {label}
      </div>
      <div
        style={{
          width, height, borderRadius: 22, overflow: "hidden", background: "#0e1621", position: "relative",
          border: "1px solid rgba(255,255,255,0.06)", boxShadow: "0 20px 60px rgba(0,0,0,0.45)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        {!current ? (
          // пока бот ничего не прислал — копим чек-лист уже показанных фич, чтобы панель не пустовала
          <div style={{ width: "100%", height: "100%", padding: 44, boxSizing: "border-box", display: "flex",
                        flexDirection: "column", gap: 22 }}>
            <div style={{ fontSize: 30, fontWeight: 700, color: "#dbe6f0", marginBottom: 6 }}>Уже показали</div>
            {captions.filter((c) => c.at <= frame).map((c) => (
              <div key={c.at} style={{
                fontSize: 27, color: "#dbe6f0", display: "flex", gap: 14,
                opacity: interpolate(frame - c.at, [0, 10], [0, 1], clampOpts),
                translate: interpolate(frame - c.at, [0, 12], ["-18px 0px", "0px 0px"], { ...clampOpts, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
              }}>
                <span style={{ color: "#6ab3f3" }}>✓</span><span>{c.text}</span>
              </div>
            ))}
            <div style={{ marginTop: "auto", fontSize: 22, color: "#7f91a4" }}>{hint}</div>
          </div>
        ) : (
          <div
            key={current.file}
            style={{
              width: "100%", height: "100%", padding: 28, boxSizing: "border-box", display: "flex",
              flexDirection: "column", gap: 18,
              opacity: interpolate(age, [0, 10], [0, 1], clampOpts),
              scale: interpolate(age, [0, 14], [0.96, 1], { ...clampOpts, easing: Easing.bezier(0.16, 1, 0.3, 1) }),
            }}
          >
            {current.kind === "photo" ? (
              <Img src={staticFile(`media/${current.file}`)}
                   style={{ flex: 1, minHeight: 0, width: "100%", objectFit: "contain", borderRadius: 14, background: "#fff" }} />
            ) : (
              <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 16, color: "#f5f5f5" }}>
                  <div style={{ width: 64, height: 64, borderRadius: 14, background: "#1f7a45", display: "flex",
                                alignItems: "center", justifyContent: "center", fontSize: 30, fontWeight: 700 }}>
                    {current.file.toLowerCase().endsWith(".xlsx") ? "X" : "📄"}
                  </div>
                  <div style={{ fontSize: 28, fontWeight: 600 }}>{current.file.replace(/^\d+_/, "")}</div>
                </div>
                {current.preview ? (
                  <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", fontSize: 17, color: "#222" }}>
                    {current.preview.rows.map((row, r) => (
                      <div key={r} style={{ display: "flex", background: r === 0 ? "#2a7de1" : r % 2 ? "#fff" : "#f3f6fa",
                                            color: r === 0 ? "#fff" : "#222", fontWeight: r === 0 ? 700 : 400 }}>
                        {row.map((cell, c) => (
                          <div key={c} style={{ flex: c === 3 ? 2.2 : 1, padding: "9px 10px", whiteSpace: "nowrap",
                                                overflow: "hidden", textOverflow: "ellipsis",
                                                borderRight: "1px solid rgba(0,0,0,0.06)" }}>{cell}</div>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
            {caption ? <div style={{ fontSize: 24, color: "#dbe6f0" }}>{caption}</div> : null}
          </div>
        )}
      </div>
    </div>
  );
};
