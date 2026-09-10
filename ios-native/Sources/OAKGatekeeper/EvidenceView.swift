import SwiftUI
import UIKit

@MainActor
struct H1EvidenceSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppState.self) private var state
    let h1: H1SignalPayload
    let alert: H1SignalAlert
    let brokerDate: String
    @State private var glossaryOpen = false
    @State private var copiedChart = false
    @State private var chartShare: OAKShareItem?
    @State private var imageTransferFailed = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    OAKPageHeader(
                        eyebrow: "H1 / EVIDENCE",
                        title: "\(alert.symbol) · H\(String(format: "%02d", alert.slotHour))",
                        subtitle: state.text(vn: "Biểu đồ nến M15 · cũ → mới", en: "M15 candlestick chart · oldest → newest")
                    )

                    HStack(spacing: 8) {
                        if let group = alert.patternGroup { OAKPill(label: group, tone: .accent) }
                        if let entry = alert.entryHour { OAKPill(label: "ENTRY H\(entry)", tone: .muted) }
                        if let signal = alert.signal {
                            OAKPill(label: signal.rawValue, tone: signal == .buy ? .buy : .sell)
                        }
                    }

                    OAKCard {
                        VStack(alignment: .leading, spacing: 11) {
                            HStack {
                                Text(state.text(vn: "BIỂU ĐỒ M15", en: "M15 CHART"))
                                    .font(OAKFont.sectionTitle)
                                    .foregroundStyle(OAKColor.text)
                                    .accessibilityAddTraits(.isHeader)
                                Spacer()
                                Text(alert.scannerSource ?? alert.symbol)
                                    .font(.caption.bold())
                                    .foregroundStyle(OAKColor.muted)
                            }
                            CandleChartView(bars: alert.sampleBars ?? [])
                                .frame(height: 230)
                        }
                    }

                    OAKCard {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(state.text(vn: "THÔNG TIN CHÍNH", en: "KEY FACTS"))
                                    .font(OAKFont.sectionTitle)
                                    .foregroundStyle(OAKColor.text)
                                    .accessibilityAddTraits(.isHeader)
                                Spacer()
                                Button { glossaryOpen.toggle() } label: {
                                    Text(state.text(vn: glossaryOpen ? "ẨN CHÚ GIẢI" : "CHÚ GIẢI", en: glossaryOpen ? "HIDE GLOSSARY" : "GLOSSARY"))
                                        .font(OAKFont.pill)
                                }
                                .buttonStyle(.borderless)
                                .accessibilityLabel(Text(state.text(vn: "Chú giải thuật ngữ", en: "Term glossary")))
                            }
                            fact(state.text(vn: "NGÀY BROKER", en: "BROKER DAY"), brokerDate)
                            fact("BLOCK", "H\(alert.slotHour)")
                            fact(state.text(vn: "VÀO LỆNH", en: "ENTRY"), alert.entryHour.map { "H\($0)" } ?? "—")
                            let facts = h1.evidenceFacts(date: brokerDate, sourceAlert: alert)
                            fact(state.text(vn: "NHÓM", en: "GROUP"), alert.patternGroup ?? "—")
                            fact(state.text(vn: "HỌ MẪU", en: "FAMILY"), familyLabel(alert.patternFamily))
                            fact(state.text(vn: "MẪU HÌNH", en: "PATTERN"), patternLabel(alert.pattern))
                            fact(state.text(vn: "NGUỒN MẪU", en: "PATTERN SRC"), facts.patternSource)
                            fact(state.text(vn: "NẾN GỐC", en: "BASE CANDLE"), facts.rawBase)
                            if !facts.signalSource.isEmpty { fact(state.text(vn: "NGUỒN CUỐI", en: "FINAL SOURCE"), facts.signalSource) }
                            fact(state.text(vn: "LUẬT", en: "RULE"), facts.rule)
                            fact(state.text(vn: "KẾT LUẬN", en: "FINAL"), facts.finalSignal)
                            if glossaryOpen {
                                Divider()
                                glossaryLine("BLOCK", state.text(vn: "Khung giờ H1 của tín hiệu.", en: "The signal's H1 hour block."))
                                glossaryLine(state.text(vn: "VÀO LỆNH", en: "ENTRY"), state.text(vn: "Giờ H1 khuyến nghị vào lệnh.", en: "Recommended H1 entry hour."))
                                glossaryLine(state.text(vn: "HỌ MẪU", en: "FAMILY"), state.text(vn: "Nhóm cấu trúc nến (GT/TG · TT/GG).", en: "Candle-structure family (GT/TG · TT/GG)."))
                                glossaryLine(state.text(vn: "MẪU HÌNH", en: "PATTERN"), state.text(vn: "Chuỗi nến tạo ra tín hiệu.", en: "The candle sequence forming the signal."))
                                glossaryLine(state.text(vn: "NẾN GỐC", en: "BASE CANDLE"), state.text(vn: "Nến H1 gốc dùng để suy tín hiệu.", en: "The base H1 candle the signal derives from."))
                                glossaryLine(state.text(vn: "KẾT LUẬN", en: "FINAL"), state.text(vn: "Hướng BUY/SELL sau khi áp luật.", en: "The BUY/SELL call after the rule is applied."))
                            }
                        }
                    }

                    if let bars = alert.sampleBars, !bars.isEmpty {
                        OAKCard {
                            VStack(alignment: .leading, spacing: 10) {
                                Text(state.text(vn: "NẾN MẪU HÌNH · MỚI → CŨ", en: "PATTERN BARS · NEWEST → OLDEST"))
                                    .font(OAKFont.sectionTitle)
                                    .foregroundStyle(OAKColor.text)
                                    .accessibilityAddTraits(.isHeader)
                                ForEach(Array(bars.enumerated()), id: \.offset) { index, bar in
                                    HStack(spacing: 10) {
                                        Text("#\(index + 1)")
                                            .font(.caption2.bold())
                                            .foregroundStyle(OAKColor.muted)
                                            .frame(width: 24, alignment: .leading)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text("\(bar.brokerDate) · \(bar.brokerTime)")
                                                .font(.caption.bold())
                                                .foregroundStyle(OAKColor.text)
                                            Text(String(format: "O %.5f · H %.5f · L %.5f · C %.5f", bar.open, bar.high, bar.low, bar.close))
                                                .font(.system(size: 10, weight: .medium, design: .monospaced))
                                                .foregroundStyle(OAKColor.muted)
                                        }
                                        Spacer()
                                        OAKPill(label: bar.direction, tone: bar.direction == "T" ? .buy : .sell)
                                    }
                                    if index < bars.count - 1 { Divider() }
                                }
                            }
                        }
                    }

                    HStack(spacing: 10) {
                        Button {
                            copyChartImage()
                        } label: {
                            Label(copiedChart ? "CHART COPIED" : "COPY CHART", systemImage: copiedChart ? "checkmark.circle.fill" : "doc.on.clipboard")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                        }
                        .buttonStyle(.glassProminent)
                        .tint(OAKColor.accent)

                        Button {
                            shareChartImage()
                        } label: {
                            Label("SHARE CHART", systemImage: "square.and.arrow.up")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                        }
                        .buttonStyle(.glass)
                    }
                    .disabled((alert.sampleBars ?? []).isEmpty)
                }
                .padding(16)
            }
            .background(OAKColor.canvas)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(state.text(vn: "Đóng", en: "Close")) { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
        .sheet(item: $chartShare) { item in
            OAKActivityView(items: [item.url])
        }
        .alert(state.text(vn: "Không thể xuất ảnh PNG", en: "Unable to export PNG"), isPresented: $imageTransferFailed) {
            Button("OK", role: .cancel) {}
        }
    }

    private func fact(_ label: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(OAKFont.label)
                .foregroundStyle(OAKColor.muted)
                .frame(width: 88, alignment: .leading)
            Text(value)
                .font(OAKFont.mono)
                .foregroundStyle(OAKColor.text)
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    private func glossaryLine(_ term: String, _ meaning: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(term)
                .font(OAKFont.label)
                .foregroundStyle(OAKColor.accent)
            Text(meaning)
                .font(OAKFont.bodySm)
                .foregroundStyle(OAKColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    private func familyLabel(_ value: String?) -> String {
        switch value {
        case "ALT": "GT/TG"
        case "SAME": "TT/GG"
        default: value ?? "—"
        }
    }

    private func patternLabel(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return "—" }
        return value.map(String.init).joined(separator: " ")
    }

    private func copyChartImage() {
        guard let image = renderChartPNG() else {
            imageTransferFailed = true
            return
        }
        copiedChart = OAKImageTransfer.copyPNG(image)
        if !copiedChart {
            imageTransferFailed = true
            return
        }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(1.4))
            copiedChart = false
        }
    }

    private func shareChartImage() {
        guard
            let image = renderChartPNG(),
            let url = OAKImageTransfer.exportPNG(
                image,
                filename: "oak-\(alert.symbol)-h\(alert.slotHour)-\(brokerDate)-\(UUID().uuidString)"
            )
        else {
            imageTransferFailed = true
            return
        }
        chartShare = OAKShareItem(url: url)
    }

    private func renderChartPNG() -> UIImage? {
        let bars = alert.sampleBars ?? []
        guard !bars.isEmpty else { return nil }
        let view = EvidenceChartClipboardView(
            title: "OAK H1 · \(alert.symbol) H\(String(format: "%02d", alert.slotHour)) · \(brokerDate)",
            subtitle: "\(alert.patternGroup ?? "—") · \(familyLabel(alert.patternFamily)) · \(alert.pattern ?? "—") · OLDEST → NEWEST",
            bars: bars
        )
        .frame(width: 900, height: 360)
        .background(Color(hex: 0xF8FAFD))
        .preferredColorScheme(.light)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        return renderer.uiImage
    }
}

@MainActor
private struct EvidenceChartClipboardView: View {
    let title: String
    let subtitle: String
    let bars: [H1SampleBar]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.system(size: 24, weight: .black, design: .monospaced))
                .foregroundStyle(Color(hex: 0x0A101A))
            Text(subtitle)
                .font(.system(size: 16, weight: .bold, design: .monospaced))
                .foregroundStyle(Color(hex: 0x4F5C70))
            CandleChartView(bars: bars)
                .frame(height: 250)
        }
        .padding(24)
        .background(Color(hex: 0xF8FAFD), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color(hex: 0x9CAABD), lineWidth: 2)
        }
        .padding(12)
    }
}

private struct CandleChartView: View {
    let bars: [H1SampleBar]

    private var chronologicalBars: [H1SampleBar] {
        bars.sorted { left, right in
            if left.brokerDate != right.brokerDate { return left.brokerDate < right.brokerDate }
            return left.hour * 60 + left.minute < right.hour * 60 + right.minute
        }
    }

    var body: some View {
        let chronological = chronologicalBars
        GeometryReader { geometry in
            if chronological.isEmpty {
                ContentUnavailableView("No M15 evidence", systemImage: "chart.xyaxis.line")
            } else {
                Canvas { context, size in
                    let maxPrice = chronological.map(\.high).max() ?? 1
                    let minPrice = chronological.map(\.low).min() ?? 0
                    let span = max(maxPrice - minPrice, 0.000001)
                    let horizontalPadding: CGFloat = 14
                    let verticalPadding: CGFloat = 12
                    let plotWidth = max(size.width - horizontalPadding * 2, 1)
                    let plotHeight = max(size.height - verticalPadding * 2, 1)
                    let step = plotWidth / CGFloat(max(chronological.count, 1))
                    let bodyWidth = min(step * 0.48, 24)

                    func y(_ price: Double) -> CGFloat {
                        verticalPadding + CGFloat((maxPrice - price) / span) * plotHeight
                    }

                    for (index, bar) in chronological.enumerated() {
                        let x = horizontalPadding + step * (CGFloat(index) + 0.5)
                        let color = bar.direction == "T" ? OAKColor.buy : OAKColor.sell
                        var wick = Path()
                        wick.move(to: CGPoint(x: x, y: y(bar.high)))
                        wick.addLine(to: CGPoint(x: x, y: y(bar.low)))
                        context.stroke(wick, with: .color(color.opacity(bar.selected ? 1 : 0.72)), lineWidth: bar.selected ? 2 : 1.3)

                        let openY = y(bar.open)
                        let closeY = y(bar.close)
                        let top = min(openY, closeY)
                        let height = max(abs(closeY - openY), 3)
                        let rect = CGRect(x: x - bodyWidth / 2, y: top, width: bodyWidth, height: height)
                        context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(color.opacity(bar.selected ? 0.95 : 0.66)))
                        context.stroke(Path(roundedRect: rect, cornerRadius: 2), with: .color(color), lineWidth: bar.selected ? 1.8 : 1)
                    }
                }
                .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay { RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(OAKColor.border, lineWidth: 1) }
            }
        }
    }
}
