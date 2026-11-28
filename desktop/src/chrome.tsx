// The window's own chrome: macOS-style traffic lights for a window drawn without native decorations. In the
// browser dev view (no Tauri) nothing is rendered.
import { getCurrentWindow } from "@tauri-apps/api/window";
import { inTauri } from "./tauri";

type Act = "close" | "minimize" | "toggleMaximize";
const LIGHTS: { act: Act; color: string; label: string }[] = [
  { act: "close", color: "#ff5f57", label: "Close window" },
  { act: "minimize", color: "#febc2e", label: "Minimize window" },
  { act: "toggleMaximize", color: "#28c840", label: "Maximize or restore window" },
];

export function WindowControls({ className }: { className?: string }) {
  if (!inTauri()) return null;
  const run = (act: Act) => () => {
    const w = getCurrentWindow();
    (act === "close" ? w.close() : act === "minimize" ? w.minimize() : w.toggleMaximize()).catch(() => {});
  };
  return (
    <div className={className} data-tauri-drag-region>
      <div className="flex items-center gap-2">
        {LIGHTS.map((l) => (
          <button key={l.act} type="button" aria-label={l.label} title={l.label} onClick={run(l.act)} className="traffic" style={{ background: l.color }} />
        ))}
      </div>
    </div>
  );
}
