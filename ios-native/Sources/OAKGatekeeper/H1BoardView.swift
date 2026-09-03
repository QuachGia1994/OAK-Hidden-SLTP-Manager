import SwiftUI
import UIKit

enum H1BoardMode: Sendable {
    case live
    case history
}

@MainActor
struct H1BoardScreen: View {
    @Environment(AppState.self) private var state
    let mode: H1BoardMode

    @State private var selectedDate = ""
    @State private var calendarOpen = false
    @State private var selectedAlert: H1SignalAlert?
    @State private var copiedSchedule = false

    private let visibleSymbols = ["XAUUSD", "GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                OAKPageHeader(
                    eyebrow: mode == .live ? "TRADING / H1 LIVE" : "TRADING / HISTORY",
                    title: mode == .live ? state.text(vn: "H1 Live", en: "H1 Live") : state.text(vn: "Lịch sử H1", en: "H1 History"),
                    subtitle: mode == .live
                        ? state.text(vn: "Ngày broker hiện tại · entry pattern M15 ICMarkets local", en: "Current broker day · local ICMarkets M15 pattern entries")
                        : state.text(vn: "Xem lại các ngày broker đã lưu mà không cần quay về màn hình live.", en: "Review retained broker days without returning to the live screen.")
                )

                if let h1 = state.payload?.h1, let date = effectiveDate(h1) {
                    boardHeader(h1: h1, date: date)

                    if mode == .history {
                        historyPicker(h1: h1, date: date)
                    }

                    H1MatrixView(
                        h1: h1,
                        date: date,
                        symbols: visibleSymbols,
                        onSelect: { selectedAlert = $0 }
                    )

                    if h1.manualCloseH16(date: date) {
                        OAKCard(tint: OAKColor.warning) {
                            HStack(alignment: .top, spacing: 11) {
                                Image(systemName: "hand.raised.fill")
                                    .foregroundStyle(OAKColor.warning)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("H16 CLOSE")
                                        .font(.system(size: 13, weight: .black, design: .monospaced))
                                        .foregroundStyle(OAKColor.warning)
                                    Text(state.text(
                                        vn: "XAUUSD đầu ngày có entry H5. CLOSE chỉ là badge khuyến nghị; ứng dụng không tự đóng lệnh.",
                                        en: "XAUUSD starts the day at entry H5. CLOSE is advisory only; the app never closes positions automatically."
                                    ))
                                    .font(.footnote.weight(.medium))
                                    .foregroundStyle(OAKColor.muted)
                                }
                            }
                        }
                    }
                } else if state.isLoading {
                    OAKCard { ProgressView(state.text(vn: "Đang tải H1…", en: "Loading H1…")) }
                } else {
                    OAKCard(tint: OAKColor.warning) {
                        Text(state.text(vn: "Đang chờ feed H1 local.", en: "Awaiting the local H1 feed."))
                            .foregroundStyle(OAKColor.muted)
                    }
                }

                if !state.errorMessage.isEmpty {
                    Text(state.errorMessage)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(OAKColor.danger)
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $calendarOpen) {
            if let h1 = state.payload?.h1 {
                BrokerCalendarSheet(
                    dates: h1.orderedDatesDescending,
                    selectedDate: effectiveDate(h1) ?? h1.latestDate,
                    onSelect: { value in
                        selectedDate = value
                        calendarOpen = false
                    }
                )
                .presentationDetents([.medium, .large])
            }
        }
        .sheet(item: $selectedAlert) { alert in
            if let h1 = state.payload?.h1, let date = effectiveDate(h1) {
                H1EvidenceSheet(alert: alert, brokerDate: date, manualClose: alert.slotHour == 16 && h1.manualCloseH16(date: date))
            }
        }
        .onAppear { syncSelectedDate() }
        .onChange(of: state.payload?.h1?.publishedAt) { _, _ in syncSelectedDate() }
    }

    private func syncSelectedDate() {
        guard let h1 = state.payload?.h1 else { return }
        if mode == .live || selectedDate.isEmpty || h1.days[selectedDate] == nil {
            selectedDate = h1.latestDate
        }
    }

    private func effectiveDate(_ h1: H1SignalPayload) -> String? {
        let candidate = mode == .live ? h1.latestDate : (selectedDate.isEmpty ? h1.latestDate : selectedDate)
        return h1.days[candidate] == nil ? h1.latestDate.nilIfEmpty : candidate.nilIfEmpty
    }

    @ViewBuilder
    private func boardHeader(h1: H1SignalPayload, date: String) -> some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 13) {
                HStack(alignment: .top, spacing: 10) {
                    VStack(alignment: .leading, spacing: 5) {
                        OAKEyebrow(text: mode == .live ? "H1 / LIVE" : "H1 / HISTORY")
                        Text(state.text(vn: "Lịch block H1", en: "H1 Block Schedule"))
                            .font(.title2.bold())
                            .foregroundStyle(OAKColor.text)
                    }
                    Spacer()
                    Button {
                        copySchedulePNG(h1: h1, date: date)
                    } label: {
                        Label(copiedSchedule ? "COPIED" : "COPY PNG", systemImage: copiedSchedule ? "checkmark.circle.fill" : "doc.on.clipboard")
                            .font(.system(size: 12, weight: .black, design: .monospaced))
                    }
                    .buttonStyle(.glass)
                }

                HStack(spacing: 0) {
                    OAKMetric(label: "BROKER DAY", value: date)
                    Divider().frame(height: 42).padding(.horizontal, 9)
                    OAKMetric(label: "UPDATED", value: shortPublished(h1.publishedAt))
                }

                HStack(spacing: 8) {
                    OAKPill(label: "FREE ACCESS", tone: .success)
                    Text(state.text(vn: "Tất cả ô entry-time H1 đã được mở", en: "All H1 entry-time cells unlocked"))
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(OAKColor.muted)
                }
            }
        }
    }

    @ViewBuilder
    private func historyPicker(h1: H1SignalPayload, date: String) -> some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 10) {
                Text(state.text(vn: "NGÀY BROKER", en: "BROKER DATE"))
                    .font(.system(size: 12, weight: .black, design: .monospaced))
                    .tracking(1.3)
                    .foregroundStyle(OAKColor.muted)
                Button {
                    calendarOpen = true
                } label: {
                    HStack {
                        Image(systemName: "calendar")
                            .foregroundStyle(OAKColor.accent)
                        Text(displayDate(date))
                            .font(.system(size: 17, weight: .black, design: .monospaced))
                            .foregroundStyle(OAKColor.text)
                        Spacer()
                        Image(systemName: "chevron.down")
                            .foregroundStyle(OAKColor.muted)
                    }
                    .padding(13)
                    .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay { RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(OAKColor.border, lineWidth: 1) }
                }
                .buttonStyle(.plain)

                Text("\(h1.orderedDatesDescending.count) \(state.text(vn: "ngày giao dịch", en: "trading days")) · \(h1.orderedDatesDescending.last ?? "—") → \(h1.latestDate)")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(OAKColor.muted)
            }
        }
    }

    private func copySchedulePNG(h1: H1SignalPayload, date: String) {
        let view = ScheduleExportView(h1: h1, date: date, symbols: visibleSymbols)
            .frame(width: 980)
            .padding(28)
            .background(OAKColor.canvas)
            .preferredColorScheme(state.themeMode.colorScheme)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        guard let image = renderer.uiImage else { return }
        UIPasteboard.general.image = image
        copiedSchedule = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(1.4))
            copiedSchedule = false
        }
    }

    private func shortPublished(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else { return value }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "vi_VN")
        formatter.timeZone = TimeZone(identifier: "Asia/Ho_Chi_Minh")
        formatter.dateFormat = "HH:mm dd-MM"
        return formatter.string(from: date)
    }

    private func displayDate(_ value: String) -> String {
        let parts = value.split(separator: "-")
        guard parts.count == 3 else { return value }
        return "\(parts[2]) / \(parts[1]) / \(parts[0])"
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

@MainActor
private struct H1MatrixView: View {
    let h1: H1SignalPayload
    let date: String
    let symbols: [String]
    let onSelect: (H1SignalAlert) -> Void

    private let symbolWidth: CGFloat = 104
    private let cellWidth: CGFloat = 82
    private let rowHeight: CGFloat = 78

    private var manualClose: Bool { h1.manualCloseH16(date: date) }

    var body: some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("BLOCK MATRIX")
                        .font(.system(size: 13, weight: .black, design: .monospaced))
                        .tracking(1.1)
                        .foregroundStyle(OAKColor.text)
                    Spacer()
                    Text("↔ \(String(localized: "Swipe"))")
                        .font(.caption2.bold())
                        .foregroundStyle(OAKColor.muted)
                }

                HStack(alignment: .top, spacing: 6) {
                    VStack(spacing: 6) {
                        matrixHeaderLabel("SYMBOL", width: symbolWidth)
                        ForEach(symbols, id: \.self) { symbol in
                            Text(symbol)
                                .font(.system(size: 14, weight: .black, design: .monospaced))
                                .foregroundStyle(OAKColor.text)
                                .frame(width: symbolWidth, height: rowHeight, alignment: .leading)
                                .padding(.leading, 10)
                                .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                        }
                    }
                    .zIndex(2)

                    ScrollView(.horizontal, showsIndicators: true) {
                        VStack(spacing: 6) {
                            HStack(spacing: 6) {
                                ForEach(h1.hours, id: \.self) { hour in
                                    matrixHourHeader(hour)
                                }
                            }
                            ForEach(symbols, id: \.self) { symbol in
                                HStack(spacing: 6) {
                                    ForEach(h1.hours, id: \.self) { hour in
                                        H1MatrixCell(
                                            alert: h1.alert(date: date, symbol: symbol, hour: hour),
                                            width: cellWidth,
                                            height: rowHeight,
                                            onSelect: onSelect
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


    @ViewBuilder
    private func matrixHourHeader(_ hour: Int) -> some View {
        VStack(spacing: 2) {
            Text("H\(String(format: "%02d", hour))")
                .font(.system(size: 13, weight: .black, design: .monospaced))
            if manualClose && hour == 16 {
                OAKPill(label: "CLOSE", tone: .warning)
                    .scaleEffect(0.78)
            }
        }
        .foregroundStyle(manualClose && hour == 16 ? OAKColor.warning : OAKColor.muted)
        .frame(width: cellWidth, height: 52)
        .background(
            manualClose && hour == 16 ? OAKColor.warning.opacity(0.14) : OAKColor.raised,
            in: RoundedRectangle(cornerRadius: 11, style: .continuous)
        )
    }

    @ViewBuilder
    private func matrixHeaderLabel(_ label: String, width: CGFloat) -> some View {
        Text(label)
            .font(.system(size: 12, weight: .black, design: .monospaced))
            .foregroundStyle(OAKColor.text)
            .frame(width: width, height: 52, alignment: .leading)
            .padding(.leading, 10)
            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

@MainActor
private struct H1MatrixCell: View {
    let alert: H1SignalAlert?
    let width: CGFloat
    let height: CGFloat
    let onSelect: (H1SignalAlert) -> Void

    var body: some View {
        Group {
            if let alert, let entry = alert.entryHour {
                Button { onSelect(alert) } label: {
                    VStack(spacing: 7) {
                        Text("H\(String(format: "%02d", entry))")
                            .font(.system(size: 16, weight: .black, design: .monospaced))
                            .foregroundStyle(OAKColor.text)
                        if let signal = alert.signal {
                            OAKPill(label: signal.rawValue, tone: signal == .buy ? .buy : .sell)
                        } else {
                            Text("—").foregroundStyle(OAKColor.muted)
                        }
                    }
                    .frame(width: width, height: height)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            } else {
                Text("—")
                    .font(.system(size: 15, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.muted.opacity(0.55))
                    .frame(width: width, height: height)
            }
        }
        .background(OAKColor.surface, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

@MainActor
private struct BrokerCalendarSheet: View {
    @Environment(\.dismiss) private var dismiss
    let dates: [String]
    let selectedDate: String
    let onSelect: (String) -> Void
    @State private var monthAnchor: Date

    private let calendar: Calendar
    private let columns = Array(repeating: GridItem(.flexible(), spacing: 5), count: 7)

    init(dates: [String], selectedDate: String, onSelect: @escaping (String) -> Void) {
        self.dates = dates
        self.selectedDate = selectedDate
        self.onSelect = onSelect
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(secondsFromGMT: 0)!
        calendar = cal
        _monthAnchor = State(initialValue: Self.date(from: selectedDate) ?? Date())
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 14) {
                HStack {
                    Button { shiftMonth(-1) } label: { Image(systemName: "chevron.left") }
                    Spacer()
                    Text(monthTitle)
                        .font(.headline.bold())
                    Spacer()
                    Button { shiftMonth(1) } label: { Image(systemName: "chevron.right") }
                }
                .padding(.horizontal, 8)

                LazyVGrid(columns: columns, spacing: 6) {
                    ForEach(["CN", "T2", "T3", "T4", "T5", "T6", "T7"], id: \.self) { weekday in
                        Text(weekday)
                            .font(.caption2.bold())
                            .foregroundStyle(OAKColor.muted)
                            .frame(maxWidth: .infinity)
                    }
                    ForEach(monthCells, id: \.self) { date in
                        let key = Self.key(from: date)
                        let active = dates.contains(key)
                        Button {
                            guard active else { return }
                            onSelect(key)
                        } label: {
                            Text("\(calendar.component(.day, from: date))")
                                .font(.system(size: 14, weight: key == selectedDate ? .black : .semibold, design: .rounded))
                                .frame(maxWidth: .infinity, minHeight: 38)
                                .foregroundStyle(key == selectedDate ? Color.white : active ? OAKColor.text : OAKColor.muted.opacity(0.35))
                                .background(key == selectedDate ? OAKColor.accent : active ? OAKColor.accent.opacity(0.08) : Color.clear, in: RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                        .disabled(!active)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(16)
            .background(OAKColor.canvas)
            .navigationTitle("Chọn ngày H1")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Đóng") { dismiss() }
                }
            }
        }
    }

    private var monthTitle: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "vi_VN")
        formatter.timeZone = calendar.timeZone
        formatter.dateFormat = "MMMM yyyy"
        return formatter.string(from: monthAnchor).capitalized
    }

    private var monthCells: [Date] {
        let comps = calendar.dateComponents([.year, .month], from: monthAnchor)
        guard let first = calendar.date(from: comps) else { return [] }
        let weekday = calendar.component(.weekday, from: first)
        let start = calendar.date(byAdding: .day, value: -(weekday - 1), to: first) ?? first
        return (0..<42).compactMap { calendar.date(byAdding: .day, value: $0, to: start) }
    }

    private func shiftMonth(_ offset: Int) {
        monthAnchor = calendar.date(byAdding: .month, value: offset, to: monthAnchor) ?? monthAnchor
    }

    private static func date(from key: String) -> Date? {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: key)
    }

    private static func key(from date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}

@MainActor
private struct ScheduleExportView: View {
    let h1: H1SignalPayload
    let date: String
    let symbols: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            OAKEyebrow(text: "OAK GATEKEEPER · H1 SCANNER")
            Text("Lịch block H1 trong ngày")
                .font(.system(size: 30, weight: .black, design: .rounded))
                .foregroundStyle(OAKColor.text)
            Text("Broker day: \(date) · MT5 ICMarkets Local · rule v\(h1.signalRuleVersion ?? 0)")
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundStyle(OAKColor.muted)
            H1MatrixView(h1: h1, date: date, symbols: symbols, onSelect: { _ in })
        }
    }
}
