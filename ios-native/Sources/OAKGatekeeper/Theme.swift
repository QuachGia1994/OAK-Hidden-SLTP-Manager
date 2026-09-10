import SwiftUI

enum OAKThemeMode: String, CaseIterable, Identifiable, Sendable {
    case light
    case dark
    case contrast

    var id: String { rawValue }

    var colorScheme: ColorScheme {
        switch self {
        case .light: .light
        case .dark, .contrast: .dark
        }
    }
}

enum OAKLocale: String, CaseIterable, Identifiable, Sendable {
    case vn = "VN"
    case en = "EN"

    var id: String { rawValue }
}

private enum OAKThemePalette {
    static var mode: OAKThemeMode {
        OAKThemeMode(rawValue: UserDefaults.standard.string(forKey: "oak.theme") ?? "light") ?? .light
    }

    static func color(light: Int, dark: Int, contrast: Int) -> Color {
        switch mode {
        case .light: Color(hex: light)
        case .dark: Color(hex: dark)
        case .contrast: Color(hex: contrast)
        }
    }
}

enum OAKColor {
    static var canvas: Color { OAKThemePalette.color(light: 0xF2F6FA, dark: 0x07111A, contrast: 0x000000) }
    static var surface: Color { OAKThemePalette.color(light: 0xF8FAFD, dark: 0x0E1926, contrast: 0x050505) }
    static var raised: Color { OAKThemePalette.color(light: 0xEEF3F8, dark: 0x142232, contrast: 0x111111) }
    static var border: Color { OAKThemePalette.color(light: 0x9CAABD, dark: 0x26384A, contrast: 0x738199) }
    static var borderStrong: Color { OAKThemePalette.color(light: 0x68788E, dark: 0x3A5067, contrast: 0xFFFFFF) }
    static var text: Color { OAKThemePalette.color(light: 0x0A101A, dark: 0xF4F7FB, contrast: 0xFFFFFF) }
    static var muted: Color { OAKThemePalette.color(light: 0x4F5C70, dark: 0x8FA2B8, contrast: 0xD1D9E6) }
    static var accent: Color { OAKThemePalette.color(light: 0x2E6DCC, dark: 0x2E6DCC, contrast: 0x66A3FF) }
    static var accentStrong: Color { OAKThemePalette.color(light: 0x174EA6, dark: 0x174EA6, contrast: 0x9BC2FF) }
    static var buy: Color { OAKThemePalette.color(light: 0x238557, dark: 0x238557, contrast: 0x45E38B) }
    static var sell: Color { OAKThemePalette.color(light: 0xC63A32, dark: 0xC63A32, contrast: 0xFF716B) }
    static var warning: Color { OAKThemePalette.color(light: 0x9B5B00, dark: 0x9B5B00, contrast: 0xFFD166) }
    static var success: Color { OAKThemePalette.color(light: 0x198754, dark: 0x198754, contrast: 0x4ADE80) }
    static var danger: Color { OAKThemePalette.color(light: 0xB42318, dark: 0xB42318, contrast: 0xFF5B5B) }
}

extension Color {
    init(hex: Int, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 8) & 0xff) / 255,
            blue: Double(hex & 0xff) / 255,
            opacity: opacity
        )
    }
}

/// Centralized OAK typography. Built on system text styles so every size honours
/// Dynamic Type (system font-scaling) instead of fixed points. Mirrors the
/// Android `OAKType` scale; smallest style is `.caption2` (~11pt) so nothing
/// renders below the 11pt legibility floor.
enum OAKFont {
    static let display = Font.system(.largeTitle, design: .rounded).weight(.black)
    static let heroTitle = Font.system(.title, design: .rounded).weight(.black)
    static let cardTitle = Font.system(.title2).weight(.bold)
    static let toolTitle = Font.system(.title3).weight(.bold)
    static let body = Font.system(.subheadline).weight(.medium)
    static let bodySm = Font.system(.footnote).weight(.medium)
    static let caption = Font.system(.caption).weight(.bold)
    static let sectionTitle = Font.system(.footnote, design: .monospaced).weight(.black)
    static let label = Font.system(.caption2, design: .monospaced).weight(.black)
    static let metricValue = Font.system(.body, design: .monospaced).weight(.black)
    static let metricBig = Font.system(.title, design: .rounded).weight(.black)
    static let mono = Font.system(.footnote, design: .monospaced).weight(.black)
    static let pill = Font.system(.caption2, design: .monospaced).weight(.black)
    static let eyebrow = Font.system(.caption2, design: .monospaced).weight(.black)
}

struct OAKCard<Content: View>: View {
    let content: Content
    var tint: Color? = nil

    init(tint: Color? = nil, @ViewBuilder content: () -> Content) {
        self.tint = tint
        self.content = content()
    }

    var body: some View {
        content
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(OAKColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(tint?.opacity(0.5) ?? OAKColor.border.opacity(0.7), lineWidth: tint == nil ? 1 : 1.4)
            }
    }
}

struct OAKEyebrow: View {
    let text: String

    var body: some View {
        Text(text.uppercased())
            .font(OAKFont.eyebrow)
            .tracking(2)
            .foregroundStyle(OAKColor.accent)
    }
}

struct OAKPageHeader: View {
    let eyebrow: String
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            OAKEyebrow(text: eyebrow)
            Text(title)
                .font(OAKFont.display)
                .foregroundStyle(OAKColor.text)
                .accessibilityAddTraits(.isHeader)
            Text(subtitle)
                .font(OAKFont.body)
                .foregroundStyle(OAKColor.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct OAKPill: View {
    let label: String
    let tone: Tone

    enum Tone: Sendable {
        case muted, accent, buy, sell, warning, success
    }

    private var color: Color {
        switch tone {
        case .muted: OAKColor.muted
        case .accent: OAKColor.accent
        case .buy: OAKColor.buy
        case .sell: OAKColor.sell
        case .warning: OAKColor.warning
        case .success: OAKColor.success
        }
    }

    var body: some View {
        Text(label)
            .font(OAKFont.pill)
            .tracking(0.7)
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(color.opacity(0.10), in: Capsule())
            .overlay { Capsule().stroke(color.opacity(0.9), lineWidth: 1.6) }
    }
}

struct OAKMetric: View {
    let label: String
    let value: String
    var valueColor: Color = OAKColor.text

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(OAKFont.label)
                .tracking(1.2)
                .foregroundStyle(OAKColor.muted)
            Text(value)
                .font(OAKFont.metricValue)
                .foregroundStyle(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// Reusable guided empty-state: decorative glyph, heading, supporting line and an
/// optional primary action. Turns blank/loading screens into helpful next steps.
struct OAKEmptyState: View {
    let title: String
    let message: String
    var actionLabel: String? = nil
    var onAction: (() -> Void)? = nil

    var body: some View {
        OAKCard(tint: OAKColor.accent) {
            VStack(spacing: 11) {
                Text("i")
                    .font(OAKFont.metricValue)
                    .foregroundStyle(OAKColor.accent)
                    .frame(width: 46, height: 46)
                    .background(OAKColor.accent.opacity(0.12), in: Circle())
                    .accessibilityHidden(true)
                Text(title)
                    .font(OAKFont.toolTitle)
                    .foregroundStyle(OAKColor.text)
                    .multilineTextAlignment(.center)
                    .accessibilityAddTraits(.isHeader)
                Text(message)
                    .font(OAKFont.bodySm)
                    .foregroundStyle(OAKColor.muted)
                    .multilineTextAlignment(.center)
                if let actionLabel, let onAction {
                    Button(action: onAction) {
                        Text(actionLabel)
                            .font(.system(.subheadline, design: .monospaced).weight(.black))
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
            }
            .frame(maxWidth: .infinity)
        }
    }
}
