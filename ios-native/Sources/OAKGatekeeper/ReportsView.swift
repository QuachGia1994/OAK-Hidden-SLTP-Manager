import Charts
import SwiftUI

@MainActor
struct ReportsView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                OAKPageHeader(
                    eyebrow: "TRADING / REPORTS",
                    title: state.text(vn: "Báo cáo", en: "Reports"),
                    subtitle: state.text(vn: "Tóm tắt tín hiệu H1 trên dữ liệu backend đã lưu.", en: "Summary of retained H1 backend signals.")
                )

                if let reports = state.payload?.reports {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                        metricCard("TOTAL", "\(reports.totalSignals)", OAKColor.accent)
                        metricCard("BALANCE", String(format: "%.1f%%", reports.signalBalancePct), OAKColor.text)
                        metricCard("BUY", "\(reports.buySignals)", OAKColor.buy)
                        metricCard("SELL", "\(reports.sellSignals)", OAKColor.sell)
                    }

                    OAKCard {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(state.text(vn: "10 NGÀY GẦN NHẤT", en: "LAST 10 DAYS"))
                                    .font(.system(size: 12, weight: .black, design: .monospaced))
                                    .tracking(1)
                                Spacer()
                                Text("SIGNAL VOLUME")
                                    .font(.caption2.bold())
                                    .foregroundStyle(OAKColor.muted)
                            }

                            Chart(reports.trend) { point in
                                BarMark(
                                    x: .value("Index", point.index),
                                    y: .value("Signals", point.value)
                                )
                                .foregroundStyle(OAKColor.accent.gradient)
                                .cornerRadius(5)
                            }
                            .chartYAxis {
                                AxisMarks(position: .leading) { _ in
                                    AxisGridLine().foregroundStyle(OAKColor.border.opacity(0.45))
                                    AxisValueLabel().foregroundStyle(OAKColor.muted)
                                }
                            }
                            .chartXAxis {
                                AxisMarks(values: visibleAxisIndices(reports.trend)) { value in
                                    AxisTick().foregroundStyle(OAKColor.borderStrong.opacity(0.6))
                                    AxisValueLabel {
                                        if let index = value.as(Int.self), let point = reports.trend.first(where: { $0.index == index }) {
                                            Text(shortDate(point.date))
                                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                                .foregroundStyle(OAKColor.muted)
                                        }
                                    }
                                }
                            }
                            .frame(height: 230)
                        }
                    }

                    OAKCard {
                        HStack(spacing: 14) {
                            Image(systemName: "info.circle.fill")
                                .foregroundStyle(OAKColor.accent)
                            Text(state.text(
                                vn: "Báo cáo chỉ đọc dữ liệu H1 đã publish; không tác động tài khoản giao dịch.",
                                en: "Reports read published H1 data only and never mutate trading accounts."
                            ))
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(OAKColor.muted)
                        }
                    }
                } else {
                    OAKCard { ProgressView() }
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
    }

    private func metricCard(_ label: String, _ value: String, _ color: Color) -> some View {
        OAKCard(tint: color) {
            VStack(alignment: .leading, spacing: 8) {
                Text(label)
                    .font(.system(size: 10, weight: .black, design: .monospaced))
                    .tracking(1.2)
                    .foregroundStyle(OAKColor.muted)
                Text(value)
                    .font(.system(size: 28, weight: .black, design: .rounded))
                    .foregroundStyle(color)
            }
        }
    }

    private func visibleAxisIndices(_ trend: [MobileReportTrend]) -> [Int] {
        guard !trend.isEmpty else { return [] }
        let last = trend.count - 1
        return trend.indices.filter { $0 == 0 || $0 == last || $0 % 2 == 0 }.map { trend[$0].index }
    }

    private func shortDate(_ value: String) -> String {
        let parts = value.split(separator: "-")
        guard parts.count == 3 else { return value }
        return "\(parts[2])/\(parts[1])"
    }
}
