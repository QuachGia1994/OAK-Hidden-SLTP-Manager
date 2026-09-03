import SwiftUI
import UIKit

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

private extension UIColor {
    convenience init(hex: Int, alpha: CGFloat = 1) {
        self.init(
            red: CGFloat((hex >> 16) & 0xff) / 255,
            green: CGFloat((hex >> 8) & 0xff) / 255,
            blue: CGFloat(hex & 0xff) / 255,
            alpha: alpha
        )
    }
}

private extension Color {
    static func adaptive(light: Int, dark: Int) -> Color {
        Color(uiColor: UIColor { traits in
            UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

enum OAKColor {
    static let canvas = Color.adaptive(light: 0xF2F6FA, dark: 0x07111A)
    static let surface = Color.adaptive(light: 0xF8FAFD, dark: 0x0E1926)
    static let raised = Color.adaptive(light: 0xEEF3F8, dark: 0x142232)
    static let border = Color.adaptive(light: 0x9CAABD, dark: 0x26384A)
    static let borderStrong = Color.adaptive(light: 0x68788E, dark: 0x3A5067)
    static let text = Color.adaptive(light: 0x0A101A, dark: 0xF4F7FB)
    static let muted = Color.adaptive(light: 0x4F5C70, dark: 0x8FA2B8)
    static let accent = Color(hex: 0x2E6DCC)
    static let accentStrong = Color(hex: 0x174EA6)
    static let buy = Color(hex: 0x238557)
    static let sell = Color(hex: 0xC63A32)
    static let warning = Color(hex: 0x9B5B00)
    static let success = Color(hex: 0x198754)
    static let danger = Color(hex: 0xB42318)
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
            .font(.system(size: 11, weight: .black, design: .monospaced))
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
                .font(.system(size: 34, weight: .black, design: .rounded))
                .foregroundStyle(OAKColor.text)
            Text(subtitle)
                .font(.system(size: 15, weight: .medium))
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
            .font(.system(size: 11, weight: .black, design: .monospaced))
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
                .font(.system(size: 10, weight: .black, design: .monospaced))
                .tracking(1.2)
                .foregroundStyle(OAKColor.muted)
            Text(value)
                .font(.system(size: 18, weight: .black, design: .monospaced))
                .foregroundStyle(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
