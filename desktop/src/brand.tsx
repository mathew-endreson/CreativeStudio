// The CreativeStudio mark, the footage tints and the tint wall: the few brand decisions the screens share.
import type { CSSProperties } from "react";

export const PRODUCT_NAME = "CreativeStudio";

/** The logo: two rounded bars, the lower one an open "E", and the purple dot. `tile` puts it on the light rounded
 *  app-icon tile (the login card, the sidebar); otherwise the glyph takes the current text colour. */
export function BrandMark({ size = 28, tile = false, className }: { size?: number; tile?: boolean; className?: string }) {
  const glyph = tile ? "#2a2a2e" : "currentColor";
  return (
    <svg width={size} height={size} viewBox="0 0 200 200" aria-hidden="true" className={className}>
      {tile && <rect width="200" height="200" rx="46" fill="#f2f2f5" />}
      <rect x="36" y="36" width="84" height="34" rx="17" fill={glyph} />
      <circle cx="152" cy="53" r="18" fill="#9b3dc8" />
      <rect x="36" y="84" width="128" height="34" rx="17" fill={glyph} />
      <rect x="36" y="132" width="128" height="34" rx="17" fill={glyph} />
      <rect x="36" y="84" width="44" height="82" rx="17" fill={glyph} />
    </svg>
  );
}

/** One of the six footage tints, chosen from the slug so a product keeps its colour everywhere. */
export function tintFor(seed: string): { n: number; bg: string; frame: string } {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const n = (h % 6) + 1;
  return { n, bg: `var(--tint-${n})`, frame: `var(--tint-${n}f)` };
}

/** Three 9:16 frame shapes on a product's tint, or real thumbnails when the engine has them. */
export function FrameTiles({ seed, thumbs = [], height = 150, className, style }: { seed: string; thumbs?: string[]; height?: number; className?: string; style?: CSSProperties }) {
  const t = tintFor(seed);
  return (
    <div className={`relative flex items-end justify-center gap-3 overflow-hidden ${className ?? ""}`} style={{ background: t.bg, height, ...style }}>
      {[0, 1, 2].map((i) => {
        const src = thumbs[i];
        const h = height * (i === 1 ? 0.74 : 0.62);
        return (
          <div
            key={i}
            className="overflow-hidden rounded-[10px] shadow-[inset_0_1px_0_rgb(255_255_255/0.18),0_10px_24px_rgb(0_0_0/0.3)]"
            style={{ width: h * (9 / 16), height: h, background: t.frame, transform: i === 1 ? "translateY(10px)" : `translateY(24px) rotate(${i === 0 ? -3 : 3}deg)` }}
          >
            {src && <img src={src} alt="" className="h-full w-full object-cover" loading="lazy" />}
          </div>
        );
      })}
    </div>
  );
}

/** The wall behind the login card: a slightly rotated field of footage-tint tiles under a dark overlay. */
export function TintWall() {
  const tiles = Array.from({ length: 48 }, (_, i) => ((i * 7) % 6) + 1);
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute top-1/2 left-1/2 grid w-[160vmax] -translate-x-1/2 -translate-y-1/2 rotate-[-8deg] grid-cols-8 gap-4 opacity-70">
        {tiles.map((n, i) => (
          <div key={i} className="aspect-[9/16] rounded-[18px]" style={{ background: `var(--tint-${n})`, boxShadow: `inset 0 0 0 1px var(--tint-${n}f)` }} />
        ))}
      </div>
      <div className="absolute inset-0 bg-[rgb(12_12_14/0.78)]" />
    </div>
  );
}
