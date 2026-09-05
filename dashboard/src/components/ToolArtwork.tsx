import { useId } from "react";

export type ToolArtworkKind = "factcheck" | "tarot" | "card" | "discover" | "daily" | "dream" | "oracle" | "mood" | "compatibility";

export function ToolArtwork({ kind }: { kind: ToolArtworkKind }) {
  const id = useId().replace(/:/g, "");
  return <svg className="oak-tool-art" data-kind={kind} viewBox="0 0 240 160" fill="none" aria-hidden="true">
    <defs>
      <radialGradient id={id}><stop stopColor="currentColor" stopOpacity=".24" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></radialGradient>
      <linearGradient id={id + "glass"} x1="0" y1="0" x2="1" y2="1"><stop stopColor="currentColor" stopOpacity=".32" /><stop offset="1" stopColor="currentColor" stopOpacity=".03" /></linearGradient>
    </defs>
    <ellipse cx="120" cy="88" rx="115" ry="70" fill={`url(#${id})`} />
    <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="120" cy="112" rx="98" ry="25" opacity=".22" transform="rotate(-12 120 112)" />
      <path d="M25 45h5m-2.5-2.5v5M200 39h8m-4-4v8M192 127h5m-2.5-2.5v5" opacity=".55" />
      {kind === "factcheck" ? <g>
        <path d="M55 32h82v98H55z" fill={`url(#${id}glass)`} /><path d="M67 48h40M67 57h29M66 111l19-27 14 16 10-12 17 23z" />
        <circle cx="147" cy="73" r="31" fill={`url(#${id}glass)`} strokeWidth="3" /><path d="m169 96 27 28" strokeWidth="9" /><path d="M130 60a21 21 0 0 1 29-2" opacity=".7" />
      </g> : kind === "tarot" || kind === "card" ? <g>
        {kind === "tarot" && <><rect x="55" y="37" width="60" height="92" rx="5" transform="rotate(-16 85 83)" fill={`url(#${id}glass)`} />
        <rect x="131" y="37" width="60" height="92" rx="5" transform="rotate(16 161 83)" fill={`url(#${id}glass)`} />
        </>}
        <rect x="91" y="22" width="64" height="108" rx="5" fill="var(--oak-bg-surface)" />
        <rect x="97" y="28" width="52" height="96" rx="3" /><circle cx="123" cy="76" r="16" />
        <path d="M123 48v8m0 40v8M95 76h8m40 0h8M104 57l6 6m26 26 6 6m0-38-6 6m-26 26-6 6M119 72h1m7 0h1m-10 11q5 4 10 0M119 39l4-5 4 5M119 113l4 5 4-5" />
      </g> : kind === "daily" ? <g>
        <circle cx="120" cy="65" r="27" fill={`url(#${id}glass)`} />
        <path d="M120 22v9m0 68v9M77 65h9m68 0h9M89 34l7 7m48 48 7 7m0-62-7 7m-48 48-7 7M37 130l39-41 27 27 32-21 62 35" /><path d="M24 140h192" opacity=".4" />
      </g> : kind === "dream" ? <g>
        <path d="M139 26a43 43 0 1 0 30 69 40 40 0 0 1-30-69Z" fill={`url(#${id}glass)`} />
        <path d="M66 132a18 18 0 0 1 0-36 24 24 0 0 1 45-6 20 20 0 0 1 28 24h21a9 9 0 0 1 0 18Z" fill="var(--oak-bg-surface)" />
        <path d="m173 44 3 8 8 3-8 3-3 8-3-8-8-3 8-3Z" />
      </g> : kind === "compatibility" ? <g>
        <path d="M112 66c-24-38-68-2-38 28l38 31 38-31c30-30-14-66-38-28Z" fill={`url(#${id}glass)`} />
        <path d="M147 39c-21-29-54-1-29 23l29 25 29-25c25-24-8-52-29-23Z" fill={`url(#${id}glass)`} /><path d="m55 38 4 9 9 4-9 4-4 9-4-9-9-4 9-4Z" />
      </g> : kind === "mood" ? <g>
        <circle cx="120" cy="77" r="42" fill={`url(#${id}glass)`} /><path d="M102 66h2m32 0h2M101 88q19 25 38 0" strokeWidth="3" />
      </g> : <g>
        <circle cx="120" cy="76" r="42" fill={`url(#${id}glass)`} /><ellipse cx="120" cy="76" rx="68" ry="22" transform="rotate(-32 120 76)" />
        <circle cx="120" cy="76" r="33" opacity=".3" />
        {kind === "discover" ? <path d="m134 51-8 31-20 19 8-31Z" fill="currentColor" fillOpacity=".6" /> : <path d="m120 49 7 20 20 7-20 7-7 20-7-20-20-7 20-7Z" fill="currentColor" fillOpacity=".35" />}
        <path d="M95 127h50l10 9H85z" />
      </g>}
    </g>
  </svg>;
}
