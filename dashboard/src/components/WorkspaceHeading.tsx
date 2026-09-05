type Locale = "EN" | "VN";
const WORKSPACES = {
  live: { number: "01", title: { EN: "H1 LIVE", VN: "H1 LIVE" }, detail: { EN: "Stay close. Trade with discipline.", VN: "Bám sát cơ hội. Giao dịch có kỷ luật." } },
  history: { number: "02", title: { EN: "HISTORY", VN: "LỊCH SỬ" }, detail: { EN: "Look back to move forward.", VN: "Xem lại để tiến xa hơn." } },
  tools: { number: "03", title: { EN: "TOOLS", VN: "CÔNG CỤ" }, detail: { EN: "More tools. A clearer perspective.", VN: "Nhiều công cụ hơn, nhiều góc nhìn hơn." } },
  factcheck: { number: "04", title: { EN: "FACT CHECK", VN: "XÁC THỰC" }, detail: { EN: "Check carefully. Find reliable information.", VN: "Kiểm tra kỹ hơn. Thông tin đáng tin cậy hơn." } },
  tarot: { number: "05", title: { EN: "TAROT", VN: "TAROT" }, detail: { EN: "Listen to your intuition. Discover yourself.", VN: "Lắng nghe trực giác. Khám phá chính mình." } },
  discover: { number: "06", title: { EN: "DISCOVER", VN: "KHÁM PHÁ" }, detail: { EN: "Small experiences. A more positive day.", VN: "Những trải nghiệm nhỏ. Một ngày tích cực hơn." } },
} as const;

export function WorkspaceHeading({ workspace, locale }: { workspace: keyof typeof WORKSPACES; locale: Locale }) {
  const copy = WORKSPACES[workspace];
  return <header className="oak-workspace-heading">
    <span aria-hidden="true">{copy.number}</span>
    <h1>{copy.title[locale]}</h1>
    <p>{copy.detail[locale]}</p>
  </header>;
}
