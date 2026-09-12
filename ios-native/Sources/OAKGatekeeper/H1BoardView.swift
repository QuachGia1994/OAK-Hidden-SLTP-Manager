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
    @State private var scheduleShare: OAKShareItem?
    @State private var imageTransferFailed = false

    private let visibleSymbols = ["XAUUSD", "GBPUSD", "GBPAUD"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                H1TipsCard()
                if let h1 = state.payload?.h1, let date = effectiveDate(h1) {
                    H1NativeCommandHero(h1: h1, locale: state.locale)
                    H1NativeMetadataStrip(h1: h1)
                    boardHeader(h1: h1, date: date)
                    historyPicker(h1: h1, date: date)

                    H1MatrixView(
                        h1: h1,
                        date: date,
                        symbols: visibleSymbols,
                        onSelect: { selectedAlert = $0 }
                    )

                } else if state.isLoading {
                    OAKCard { ProgressView(state.text(vn: "Đang tải H1…", en: "Loading H1…")) }
                } else {
                    OAKEmptyState(
                        title: state.text(vn: "Chưa có dữ liệu H1", en: "No H1 data yet"),
                        message: state.text(
                            vn: "Đang chờ feed H1 local từ backend. Kiểm tra bridge MT5/local đang chạy rồi làm mới.",
                            en: "Waiting for the local H1 feed from the backend. Make sure the MT5/local bridge is running, then refresh."
                        ),
                        actionLabel: state.text(vn: "LÀM MỚI", en: "REFRESH"),
                        onAction: { Task { await state.refresh(forceLoading: true) } }
                    )
                }

                if !state.errorMessage.isEmpty {
                    OAKCard(tint: OAKColor.danger) {
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(state.text(vn: "Lỗi kết nối", en: "Connection error"))
                                    .font(OAKFont.label)
                                    .foregroundStyle(OAKColor.danger)
                                Text(state.errorMessage)
                                    .font(.footnote.weight(.semibold))
                                    .foregroundStyle(OAKColor.text)
                            }
                            Spacer()
                            Button {
                                Task { await state.refresh() }
                            } label: {
                                Text(state.text(vn: "THỬ LẠI", en: "RETRY"))
                                    .font(OAKFont.pill)
                            }
                            .buttonStyle(.bordered)
                        }
                        .accessibilityElement(children: .combine)
                    }
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
                H1EvidenceSheet(h1: h1, alert: alert, brokerDate: date)
            }
        }
        .sheet(item: $scheduleShare) { item in
            OAKActivityView(items: [item.url])
        }
        .alert(state.text(vn: "Không thể xuất ảnh PNG", en: "Unable to export PNG"), isPresented: $imageTransferFailed) {
            Button("OK", role: .cancel) {}
        }
        .onAppear { syncSelectedDate() }
        .onChange(of: state.payload?.h1?.publishedAt) { _, _ in syncSelectedDate() }
    }

    private func syncSelectedDate() {
        guard let h1 = state.payload?.h1 else { return }
        if selectedDate.isEmpty || h1.days[selectedDate] == nil {
            selectedDate = h1.latestDate
        }
    }

    private func effectiveDate(_ h1: H1SignalPayload) -> String? {
        let candidate = selectedDate.isEmpty ? h1.latestDate : selectedDate
        return h1.days[candidate] == nil ? h1.latestDate.nilIfEmpty : candidate.nilIfEmpty
    }

    @ViewBuilder
    private func boardHeader(h1: H1SignalPayload, date: String) -> some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 13) {
                HStack(alignment: .top, spacing: 10) {
                    VStack(alignment: .leading, spacing: 5) {
                        OAKEyebrow(text: date == h1.latestDate ? "H1 / LIVE" : "H1 / HISTORY")
                        Text(state.text(vn: "H1 Live + Lịch sử", en: "H1 Live + History"))
                            .font(.title2.bold())
                            .foregroundStyle(OAKColor.text)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        Button {
                            copySchedulePNG(h1: h1, date: date)
                        } label: {
                            Label(copiedSchedule ? "COPIED" : "COPY PNG", systemImage: copiedSchedule ? "checkmark.circle.fill" : "doc.on.clipboard")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                        }
                        .buttonStyle(.glass)
                        Button {
                            shareSchedulePNG(h1: h1, date: date)
                        } label: {
                            Label("SHARE PNG", systemImage: "square.and.arrow.up")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                        }
                        .buttonStyle(.glass)
                    }
                }

                HStack(spacing: 0) {
                    OAKMetric(label: state.text(vn: "NGÀY BROKER", en: "BROKER DAY"), value: date)
                    Divider().frame(height: 42).padding(.horizontal, 9)
                    OAKMetric(label: state.text(vn: "CẬP NHẬT", en: "UPDATED"), value: shortPublished(h1.publishedAt))
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
                .accessibilityLabel(Text(state.text(vn: "Chọn ngày broker, hiện tại \(displayDate(date))", en: "Choose broker date, currently \(displayDate(date))")))

                Text("\(h1.orderedDatesDescending.count) \(state.text(vn: "ngày giao dịch", en: "trading days")) · \(h1.orderedDatesDescending.last ?? "—") → \(h1.latestDate)")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(OAKColor.muted)
            }
        }
    }

    private func copySchedulePNG(h1: H1SignalPayload, date: String) {
        guard let image = renderSchedulePNG(h1: h1, date: date) else {
            imageTransferFailed = true
            return
        }
        copiedSchedule = OAKImageTransfer.copyPNG(image)
        if !copiedSchedule {
            imageTransferFailed = true
            return
        }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(1.4))
            copiedSchedule = false
        }
    }

    private func shareSchedulePNG(h1: H1SignalPayload, date: String) {
        guard
            let image = renderSchedulePNG(h1: h1, date: date),
            let url = OAKImageTransfer.exportPNG(image, filename: "oak-h1-scanner-\(date)-\(UUID().uuidString)")
        else {
            imageTransferFailed = true
            return
        }
        scheduleShare = OAKShareItem(url: url)
    }

    private func renderSchedulePNG(h1: H1SignalPayload, date: String) -> UIImage? {
        let view = ScheduleExportView(h1: h1, date: date, symbols: visibleSymbols)
            .frame(width: 980)
            .padding(28)
            .background(OAKColor.canvas)
            .preferredColorScheme(state.themeMode.colorScheme)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        return renderer.uiImage
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

@MainActor
private struct H1TipsCard: View {
    @Environment(AppState.self) private var state
    @AppStorage("oak.h1.tipsDismissed") private var dismissed = false

    var body: some View {
        if !dismissed {
            OAKCard(tint: OAKColor.accent) {
                VStack(alignment: .leading, spacing: 9) {
                    HStack {
                        Text(state.text(vn: "BẮT ĐẦU NHANH", en: "QUICK START"))
                            .font(OAKFont.label)
                            .tracking(1.2)
                            .foregroundStyle(OAKColor.accent)
                            .accessibilityAddTraits(.isHeader)
                        Spacer()
                        Button { dismissed = true } label: {
                            Text(state.text(vn: "ĐÃ HIỂU", en: "GOT IT"))
                                .font(OAKFont.pill)
                        }
                        .buttonStyle(.borderless)
                        .accessibilityLabel(Text(state.text(vn: "Ẩn hướng dẫn bắt đầu", en: "Dismiss getting-started tips")))
                    }
                    tip(state.text(vn: "Chạm ô BUY/SELL để xem bằng chứng signal.", en: "Tap a BUY/SELL cell to inspect its signal evidence."))
                    tip(state.text(vn: "Đổi NGÀY BROKER để xem lịch sử H1 đã lưu.", en: "Change the BROKER DATE to review retained H1 history."))
                    tip(state.text(vn: "Kéo xuống để làm mới feed.", en: "Pull down to refresh the feed."))
                }
            }
        }
    }

    private func tip(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text("•").foregroundStyle(OAKColor.accent).accessibilityHidden(true)
            Text(text).font(OAKFont.bodySm).foregroundStyle(OAKColor.muted)
        }
        .accessibilityElement(children: .combine)
    }
}

@MainActor
private struct H1NativeCommandHero: View {
    let h1: H1SignalPayload
    let locale: OAKLocale

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 9) {
                OAKEyebrow(text: "OAK / TRÍ TUỆ THUẬT TOÁN")
                HStack(alignment: .firstTextBaseline, spacing: 9) {
                    Text("01")
                        .font(.system(size: 13, weight: .black, design: .monospaced))
                        .foregroundStyle(OAKColor.accent)
                    Text("H1 LIVE")
                        .font(.system(size: 30, weight: .black, design: .rounded))
                        .foregroundStyle(OAKColor.text)
                }
                Text(locale == .vn ? "Bám sát tín hiệu. Giao dịch có kỷ luật." : "Track the signal. Trade with discipline.")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(OAKColor.muted)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 7) {
                    OAKPill(label: locale == .vn ? "DỮ LIỆU ĐÃ LƯU" : "RETAINED DATA", tone: .success)
                    Text("v\(h1.signalRuleVersion ?? 0)")
                        .font(.system(size: 11, weight: .black, design: .monospaced))
                        .foregroundStyle(OAKColor.muted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            OAKNativeOrbitCore()
                .frame(width: 118, height: 118)
                .accessibilityHidden(true)
        }
        .padding(16)
        .background(
            LinearGradient(
                colors: [OAKColor.surface, OAKColor.canvas],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 18, style: .continuous)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(OAKColor.border.opacity(0.72), lineWidth: 1)
        }
    }
}

@MainActor
private struct H1NativeMetadataStrip: View {
    @Environment(AppState.self) private var state
    let h1: H1SignalPayload
    private let columns = [GridItem(.flexible(), spacing: 0), GridItem(.flexible(), spacing: 0)]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 0) {
            metadata(label: state.text(vn: "NGUỒN DỮ LIỆU", en: "DATA SOURCE"), value: "MT5 ICMarkets Local")
            metadata(label: state.text(vn: "NHỊP DỮ LIỆU", en: "DATA CADENCE"), value: "H03–H14 · XAU M15 + derived GBPUSD/GBPAUD")
            metadata(label: state.text(vn: "NGÀY ĐÃ LƯU", en: "STORED DAYS"), value: "\(h1.orderedDatesDescending.count) \(state.text(vn: "ngày", en: "days"))")
            metadata(label: state.text(vn: "NGÀY MỚI NHẤT", en: "LATEST DAY"), value: h1.latestDate)
        }
        .background(OAKColor.surface, in: RoundedRectangle(cornerRadius: 15, style: .continuous))
        .overlay { RoundedRectangle(cornerRadius: 15).stroke(OAKColor.border.opacity(0.7), lineWidth: 1) }
    }

    private func metadata(label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label)
                .font(OAKFont.label)
                .tracking(1.1)
                .foregroundStyle(OAKColor.muted)
            Text(value)
                .font(OAKFont.mono)
                .foregroundStyle(OAKColor.text)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity, minHeight: 62, alignment: .leading)
        .padding(.horizontal, 11)
        .padding(.vertical, 9)
        .overlay(alignment: .bottom) { Rectangle().fill(OAKColor.border.opacity(0.45)).frame(height: 0.5) }
        .accessibilityElement(children: .combine)
    }
}

@MainActor
struct OAKNativeOrbitCore: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var animationStart = Date()
    var label: String = "H1"

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: reduceMotion || scenePhase != .active)) { context in
            let elapsed = reduceMotion || scenePhase != .active
                ? 0
                : max(0, context.date.timeIntervalSince(animationStart))

            ZStack {
                Canvas { context, size in
                    drawOrbitScene(&context, size: size, elapsed: elapsed)
                }

                Text(label)
                    .font(.system(size: label.count > 2 ? 11 : 15, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.text)
                    .frame(width: 41, height: 41)
                    .background(OAKColor.surface.opacity(0.90), in: Circle())
                    .overlay { Circle().stroke(OAKColor.accent, lineWidth: 1) }
            }
            .shadow(color: OAKColor.accent.opacity(0.22), radius: 14)
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { animationStart = Date() }
            }
            .onChange(of: reduceMotion) { _, _ in
                animationStart = Date()
            }
        }
    }

    private func drawOrbitScene(_ context: inout GraphicsContext, size: CGSize, elapsed: Double) {
        let center = CGPoint(x: size.width / 2, y: size.height / 2)

        drawCircle(&context, center: center, radius: 54, rotation: (66, 0, -14), opacity: 0.70)
        drawCircle(&context, center: center, radius: 48, rotation: (66, 0, 34), opacity: 0.62, dash: [4, 3])
        drawCircle(&context, center: center, radius: 25, rotation: (62, 0, -28), opacity: 0.88)

        drawOrbit(&context, center: center, radius: 54, rotation: (64, 0, 12 + cycle(elapsed, duration: 10) * 360), opacity: 0.44, dots: [-90, 18, 156])
        let vertical = verticalRotation(cycle(elapsed, duration: 8))
        drawOrbit(&context, center: center, radius: 49.5, rotation: vertical, opacity: 0.58, dots: [-90, 156])
        drawOrbit(&context, center: center, radius: 51, rotation: (58, 42, 24 - cycle(elapsed, duration: 13) * 360), opacity: 0.32, dots: [-90, 156])

        let globe = globeRotation(elapsed / 18)
        for longitude in stride(from: 0.0, through: 150.0, by: 30.0) {
            drawGlobeCircle(&context, center: center, radius: 34, rotation: globe, longitude: longitude, opacity: 0.65)
        }
        drawEquator(&context, center: center, radius: 34, rotation: globe, opacity: 0.72)

    }

    private func drawCircle(
        _ context: inout GraphicsContext,
        center: CGPoint,
        radius: Double,
        rotation: (Double, Double, Double),
        opacity: Double,
        dash: [CGFloat] = []
    ) {
        let paths = projectedCircle(radius: radius, rotation: rotation, center: center)
        stroke(&context, paths.back, opacity: opacity * 0.28, dash: dash)
        stroke(&context, paths.front, opacity: opacity, dash: dash)
    }

    private func drawOrbit(
        _ context: inout GraphicsContext,
        center: CGPoint,
        radius: Double,
        rotation: (Double, Double, Double),
        opacity: Double,
        dots: [Double]
    ) {
        drawCircle(&context, center: center, radius: radius, rotation: rotation, opacity: opacity)
        for angle in dots {
            let point = projected(OAKVector3(x: cos(radians(angle)), y: sin(radians(angle)), z: 0), rotation: rotation, radius: radius, center: center)
            let dotRadius = 2.05
            let dot = Path(ellipseIn: CGRect(x: point.location.x - dotRadius, y: point.location.y - dotRadius, width: dotRadius * 2, height: dotRadius * 2))
            context.fill(dot, with: .color(OAKColor.accent.opacity(point.depth >= 0 ? 0.98 : 0.30)))
        }
    }

    private func drawGlobeCircle(
        _ context: inout GraphicsContext,
        center: CGPoint,
        radius: Double,
        rotation: (Double, Double, Double),
        longitude: Double,
        opacity: Double
    ) {
        let points = (0..<96).map { index in
            let angle = Double(index) / 96 * .pi * 2
            return OAKVector3(x: cos(angle) * cos(radians(longitude)), y: sin(angle), z: -cos(angle) * sin(radians(longitude)))
        }
        let paths = projected(points, rotation: rotation, radius: radius, center: center)
        stroke(&context, paths.back, opacity: opacity * 0.20)
        stroke(&context, paths.front, opacity: opacity * 0.82)
    }

    private func drawEquator(
        _ context: inout GraphicsContext,
        center: CGPoint,
        radius: Double,
        rotation: (Double, Double, Double),
        opacity: Double
    ) {
        let points = (0..<96).map { index in
            let angle = Double(index) / 96 * .pi * 2
            return OAKVector3(x: cos(angle), y: 0, z: sin(angle))
        }
        let paths = projected(points, rotation: rotation, radius: radius, center: center)
        stroke(&context, paths.back, opacity: opacity * 0.20)
        stroke(&context, paths.front, opacity: opacity * 0.88)
    }

    private func stroke(_ context: inout GraphicsContext, _ path: Path, opacity: Double, dash: [CGFloat] = []) {
        context.stroke(path, with: .color(OAKColor.accent.opacity(opacity)), style: StrokeStyle(lineWidth: 0.9, lineCap: .round, dash: dash))
    }

    private func projectedCircle(radius: Double, rotation: (Double, Double, Double), center: CGPoint) -> (back: Path, front: Path) {
        projected((0..<96).map { index in
            let angle = Double(index) / 96 * .pi * 2
            return OAKVector3(x: cos(angle), y: sin(angle), z: 0)
        }, rotation: rotation, radius: radius, center: center)
    }

    private func projected(_ points: [OAKVector3], rotation: (Double, Double, Double), radius: Double, center: CGPoint) -> (back: Path, front: Path) {
        var back = Path()
        var front = Path()
        let transformed = points.map { projected($0, rotation: rotation, radius: radius, center: center) }
        var previousSide: Bool?
        for index in transformed.indices {
            let next = transformed[(index + 1) % transformed.count]
            let current = transformed[index]
            let isFront = current.depth + next.depth >= 0
            if isFront {
                if previousSide == true { front.addLine(to: next.location) }
                else {
                    front.move(to: current.location)
                    front.addLine(to: next.location)
                }
            } else if previousSide == false { back.addLine(to: next.location) }
            else {
                back.move(to: current.location)
                back.addLine(to: next.location)
            }
            previousSide = isFront
        }
        return (back, front)
    }

    private func projected(_ point: OAKVector3, rotation: (Double, Double, Double), radius: Double, center: CGPoint) -> (location: CGPoint, depth: Double) {
        let rotated = rotate(point, x: rotation.0, y: rotation.1, z: rotation.2)
        let scale = 1 + rotated.z * 0.06
        return (CGPoint(x: center.x + rotated.x * radius * scale, y: center.y + rotated.y * radius * scale), rotated.z)
    }

    private func verticalRotation(_ progress: Double) -> (Double, Double, Double) {
        let start = (0.0, 68.0, -16.0)
        let middle = (180.0, 18.0, 12.0)
        let end = (360.0, 68.0, -16.0)
        return progress < 0.5
            ? interpolate(start, middle, amount: progress * 2)
            : interpolate(middle, end, amount: (progress - 0.5) * 2)
    }

    private func globeRotation(_ progress: Double) -> (Double, Double, Double) {
        let cycle = Int(progress)
        let fraction = progress - Double(cycle)
        let eased = 0.5 - 0.5 * cos((cycle.isMultiple(of: 2) ? fraction : 1 - fraction) * .pi)
        return interpolate((-18, -8, -22), (-10, 34, 14), amount: eased)
    }

    private func interpolate(_ a: (Double, Double, Double), _ b: (Double, Double, Double), amount: Double) -> (Double, Double, Double) {
        (a.0 + (b.0 - a.0) * amount, a.1 + (b.1 - a.1) * amount, a.2 + (b.2 - a.2) * amount)
    }

    private func cycle(_ elapsed: Double, duration: Double) -> Double {
        elapsed.truncatingRemainder(dividingBy: duration) / duration
    }

    private func rotate(_ point: OAKVector3, x: Double, y: Double, z: Double) -> OAKVector3 {
        let zRotated = OAKVector3(x: point.x * cos(radians(z)) - point.y * sin(radians(z)), y: point.x * sin(radians(z)) + point.y * cos(radians(z)), z: point.z)
        let yRotated = OAKVector3(x: zRotated.x * cos(radians(y)) + zRotated.z * sin(radians(y)), y: zRotated.y, z: -zRotated.x * sin(radians(y)) + zRotated.z * cos(radians(y)))
        return OAKVector3(x: yRotated.x, y: yRotated.y * cos(radians(x)) - yRotated.z * sin(radians(x)), z: yRotated.y * sin(radians(x)) + yRotated.z * cos(radians(x)))
    }

    private func radians(_ degrees: Double) -> Double { degrees * .pi / 180 }
}

private struct OAKVector3 {
    let x: Double
    let y: Double
    let z: Double
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

@MainActor
private struct H1MatrixView: View {
    @Environment(AppState.self) private var state
    let h1: H1SignalPayload
    let date: String
    let symbols: [String]
    let onSelect: (H1SignalAlert) -> Void

    private let symbolWidth: CGFloat = 104
    private let cellWidth: CGFloat = 82
    private let rowHeight: CGFloat = 78

    var body: some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text(state.text(vn: "MA TRẬN BLOCK", en: "BLOCK MATRIX"))
                        .font(OAKFont.sectionTitle)
                        .tracking(1.1)
                        .foregroundStyle(OAKColor.text)
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    Text("↔ \(state.text(vn: "Vuốt", en: "Swipe"))")
                        .font(.caption2.bold())
                        .foregroundStyle(OAKColor.muted)
                }

                HStack(alignment: .top, spacing: 6) {
                    VStack(spacing: 6) {
                        matrixHeaderLabel("", width: symbolWidth)
                        matrixRowLabel(state.text(vn: "GIỜ VÀO", en: "ENTRY TIME"), compact: true)
                        ForEach(symbols, id: \.self) { symbol in
                            matrixRowLabel(symbol)
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
                            HStack(spacing: 6) {
                                ForEach(h1.hours, id: \.self) { hour in
                                    H1EntryTimeCell(
                                        alert: h1.alert(date: date, symbol: "XAUUSD", hour: hour),
                                        width: cellWidth,
                                        height: rowHeight,
                                        highlighted: false
                                    )
                                }
                            }
                            ForEach(symbols, id: \.self) { symbol in
                                HStack(spacing: 6) {
                                    ForEach(h1.hours, id: \.self) { hour in
                                        H1SignalCell(
                                            alert: h1.alert(date: date, symbol: symbol, hour: hour),
                                            symbol: symbol,
                                            hour: hour,
                                            width: cellWidth,
                                            height: rowHeight,
                                            highlighted: false,
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
        Text("H\(String(format: "%02d", hour))")
            .font(.system(size: 13, weight: .black, design: .monospaced))
            .foregroundStyle(OAKColor.muted)
            .frame(width: cellWidth, height: 52)
            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
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

    @ViewBuilder
    private func matrixRowLabel(_ label: String, compact: Bool = false) -> some View {
        Text(label)
            .font(.system(size: compact ? 12 : 14, weight: .black, design: .monospaced))
            .foregroundStyle(OAKColor.text)
            .lineLimit(1)
            .minimumScaleFactor(0.8)
            .frame(width: symbolWidth, height: rowHeight, alignment: .leading)
            .padding(.leading, 10)
            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

@MainActor
private struct H1EntryTimeCell: View {
    let alert: H1SignalAlert?
    let width: CGFloat
    let height: CGFloat
    let highlighted: Bool

    var body: some View {
        Group {
            if let entry = alert?.entryHour {
                Text("H\(String(format: "%02d", entry))")
                    .font(.system(size: 18, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.accent)
            } else {
                Text("—")
                    .font(.system(size: 15, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.muted.opacity(0.55))
            }
        }
        .frame(width: width, height: height)
        .background((highlighted ? OAKColor.warning.opacity(0.11) : OAKColor.surface), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 11)
                .stroke(highlighted ? OAKColor.warning.opacity(0.75) : OAKColor.border.opacity(0.45), lineWidth: highlighted ? 1.5 : 0.8)
        }
    }
}

@MainActor
private struct H1SignalCell: View {
    let alert: H1SignalAlert?
    let symbol: String
    let hour: Int
    let width: CGFloat
    let height: CGFloat
    let highlighted: Bool
    let onSelect: (H1SignalAlert) -> Void

    var body: some View {
        Group {
            if let alert, let signal = alert.signal {
                Button { onSelect(alert) } label: {
                    OAKPill(label: signal.rawValue, tone: signal == .buy ? .buy : .sell)
                        .frame(width: width, height: height)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("\(symbol) H\(String(format: "%02d", hour)) \(signal.rawValue)"))
            } else {
                Text("—")
                    .font(.system(size: 15, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.muted.opacity(0.55))
                    .frame(width: width, height: height)
                    .accessibilityHidden(true)
            }
        }
        .background((highlighted ? OAKColor.warning.opacity(0.08) : OAKColor.surface), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 11)
                .stroke(highlighted ? OAKColor.warning.opacity(0.65) : OAKColor.border.opacity(0.35), lineWidth: highlighted ? 1.4 : 0.7)
        }
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
private struct ScheduleExportMatrix: View {
    let h1: H1SignalPayload
    let date: String
    let symbols: [String]

    private let symbolWidth: CGFloat = 124
    private let cellWidth: CGFloat = 118
    private let rowHeight: CGFloat = 74

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("BLOCK MATRIX")
                    .font(.system(size: 13, weight: .black, design: .monospaced))
                    .tracking(1.1)
                    .foregroundStyle(OAKColor.text)
                Spacer()
                Text("ALL BLOCKS")
                    .font(.system(size: 11, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.muted)
            }

            HStack(alignment: .top, spacing: 6) {
                VStack(spacing: 6) {
                    exportLabel("SYMBOL", width: symbolWidth, height: 54)
                    ForEach(symbols, id: \.self) { symbol in
                        exportLabel(symbol, width: symbolWidth, height: rowHeight)
                    }
                }

                VStack(spacing: 6) {
                    HStack(spacing: 6) {
                        ForEach(h1.hours, id: \.self) { hour in
                            exportHourHeader(hour)
                        }
                    }
                    ForEach(symbols, id: \.self) { symbol in
                        HStack(spacing: 6) {
                            ForEach(h1.hours, id: \.self) { hour in
                                exportCell(alert: h1.alert(date: date, symbol: symbol, hour: hour))
                            }
                        }
                    }
                }
            }
        }
        .padding(14)
        .background(OAKColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(OAKColor.border, lineWidth: 1)
        }
    }

    @ViewBuilder
    private func exportHourHeader(_ hour: Int) -> some View {
        Text("H\(String(format: "%02d", hour))")
            .font(.system(size: 13, weight: .black, design: .monospaced))
            .foregroundStyle(OAKColor.muted)
            .frame(width: cellWidth, height: 54)
            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
    }

    @ViewBuilder
    private func exportCell(alert: H1SignalAlert?) -> some View {
        VStack(spacing: 7) {
            if let alert, let entry = alert.entryHour {
                Text("H\(String(format: "%02d", entry))")
                    .font(.system(size: 16, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.text)
                if let signal = alert.signal {
                    OAKPill(label: signal.rawValue, tone: signal == .buy ? .buy : .sell)
                } else {
                    Text("—")
                        .font(.system(size: 15, weight: .black, design: .monospaced))
                        .foregroundStyle(OAKColor.muted)
                }
            } else {
                Text("—")
                    .font(.system(size: 15, weight: .black, design: .monospaced))
                    .foregroundStyle(OAKColor.muted.opacity(0.55))
            }
        }
        .frame(width: cellWidth, height: rowHeight)
        .background(OAKColor.surface, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .stroke(OAKColor.border.opacity(0.6), lineWidth: 0.8)
        }
    }

    private func exportLabel(_ value: String, width: CGFloat, height: CGFloat) -> some View {
        Text(value)
            .font(.system(size: value == "SYMBOL" ? 12 : 14, weight: .black, design: .monospaced))
            .foregroundStyle(OAKColor.text)
            .frame(width: width, height: height, alignment: .leading)
            .padding(.leading, 10)
            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 11, style: .continuous))
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
            ScheduleExportMatrix(h1: h1, date: date, symbols: symbols)
        }
    }
}
