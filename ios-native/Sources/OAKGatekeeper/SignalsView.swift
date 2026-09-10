import SwiftUI

@MainActor
struct SignalsView: View {
    @Environment(AppState.self) private var state
    @State private var filter: Filter = .all
    @State private var selectedAlert: H1SignalAlert?

    private enum Filter: String, CaseIterable, Identifiable {
        case all = "ALL"
        case buy = "BUY"
        case sell = "SELL"
        var id: String { rawValue }
    }

    private let visibleSymbols = ["XAUUSD"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                OAKPageHeader(
                    eyebrow: "TRADING / SIGNALS",
                    title: state.text(vn: "Tín hiệu", en: "Signals"),
                    subtitle: state.text(vn: "Radar BUY/SELL theo H1 và drill-down evidence M15.", en: "BUY/SELL H1 radar with M15 evidence drill-down.")
                )

                Picker("Filter", selection: $filter) {
                    ForEach(Filter.allCases) { item in Text(item.rawValue).tag(item) }
                }
                .pickerStyle(.segmented)

                if let h1 = state.payload?.h1, !h1.latestDate.isEmpty {
                    let date = h1.latestDate
                    let rows = filteredAlerts(h1: h1, date: date)

                    HStack {
                        Text(state.text(vn: "HOẠT ĐỘNG H1", en: "H1 ACTIVITY"))
                            .font(OAKFont.sectionTitle)
                            .tracking(1)
                            .accessibilityAddTraits(.isHeader)
                        Spacer()
                        Text(date)
                            .font(.caption.bold())
                            .foregroundStyle(OAKColor.muted)
                    }

                    ForEach(rows) { alert in
                        Button { selectedAlert = alert } label: {
                            OAKCard(tint: alert.signal == .buy ? OAKColor.buy : alert.signal == .sell ? OAKColor.sell : nil) {
                                HStack(alignment: .center, spacing: 12) {
                                    VStack(alignment: .leading, spacing: 6) {
                                        HStack(spacing: 8) {
                                            Text(alert.symbol)
                                                .font(.system(size: 18, weight: .black, design: .rounded))
                                            Text("H\(String(format: "%02d", alert.slotHour))")
                                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                                .foregroundStyle(OAKColor.muted)
                                        }
                                        HStack(spacing: 7) {
                                            if let entry = alert.entryHour { OAKPill(label: "ENTRY H\(entry)", tone: .muted) }
                                            if let group = alert.patternGroup { OAKPill(label: group, tone: .accent) }
                                        }
                                    }
                                    Spacer()
                                    if let signal = alert.signal {
                                        OAKPill(label: signal.rawValue, tone: signal == .buy ? .buy : .sell)
                                    } else {
                                        Text("—").foregroundStyle(OAKColor.muted)
                                    }
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityElement(children: .combine)
                    }

                    if rows.isEmpty {
                        OAKEmptyState(
                            title: state.text(vn: "Không có tín hiệu khớp", en: "No matching alerts"),
                            message: filter == .all
                                ? state.text(vn: "Chưa có tín hiệu BUY/SELL cho ngày H1 mới nhất.", en: "No BUY/SELL alerts for the latest H1 day yet.")
                                : state.text(vn: "Không có tín hiệu \(filter.rawValue) cho ngày này. Thử xem tất cả.", en: "No \(filter.rawValue) alerts for this day. Try viewing all."),
                            actionLabel: filter == .all ? nil : state.text(vn: "XEM TẤT CẢ", en: "VIEW ALL"),
                            onAction: filter == .all ? nil : ({ filter = .all })
                        )
                    }
                } else {
                    OAKEmptyState(
                        title: state.text(vn: "Chưa có feed H1", en: "No H1 feed"),
                        message: state.text(vn: "Đang chờ dữ liệu H1 từ backend.", en: "Waiting for H1 data from the backend.")
                    )
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
        .sheet(item: $selectedAlert) { alert in
            if let h1 = state.payload?.h1 {
                H1EvidenceSheet(h1: h1, alert: alert, brokerDate: h1.latestDate)
            }
        }
    }

    private func filteredAlerts(h1: H1SignalPayload, date: String) -> [H1SignalAlert] {
        h1.alerts(date: date, visibleSymbols: visibleSymbols)
            .filter { $0.entryHour != nil }
            .filter { alert in
                switch filter {
                case .all: return alert.signal != nil
                case .buy: return alert.signal == .buy
                case .sell: return alert.signal == .sell
                }
            }
    }
}
