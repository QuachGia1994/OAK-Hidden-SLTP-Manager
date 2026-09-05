export type ToolArtworkKind = "factcheck" | "tarot" | "card" | "discover" | "daily" | "dream" | "oracle" | "mood" | "compatibility";

/** Decorative atlas; text, controls and actual Tarot results remain semantic DOM. */
export function ToolArtwork({ kind }: { kind: ToolArtworkKind }) {
  return <span className="oak-tool-art" data-kind={kind} aria-hidden="true" />;
}
