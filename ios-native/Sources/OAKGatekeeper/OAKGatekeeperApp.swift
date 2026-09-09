import SwiftUI

@main
@MainActor
struct OAKGatekeeperApp: App {
    @State private var state = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .id(state.themeMode)
                .environment(state)
                .preferredColorScheme(state.themeMode.colorScheme)
                .tint(OAKColor.accent)
                .background(OAKColor.canvas)
        }
    }
}

@MainActor
private struct RootView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        Group {
            if state.isUnlocked {
                Group {
                    if state.payload == nil && state.errorMessage.isEmpty {
                        OAKLaunchLoadingView()
                    } else {
                        MainTabView()
                    }
                }
                .task(id: state.apiKey) { await state.refreshLoop() }
            } else {
                UnlockView()
            }
        }
        .background(OAKColor.canvas.ignoresSafeArea())
    }
}

@MainActor
private struct OAKLaunchLoadingView: View {
    var body: some View {
        VStack {
            HStack(spacing: 18) {
                OAKNativeOrbitCore(label: "OAK")
                    .frame(width: 118, height: 118)

                VStack(alignment: .leading, spacing: 7) {
                    Text("OAK GATEKEEPER")
                        .font(.system(size: 13, weight: .black, design: .monospaced))
                        .tracking(1.2)
                        .foregroundStyle(OAKColor.accent)
                    Text("Đang mở OAK")
                        .font(.system(size: 20, weight: .black, design: .rounded))
                        .foregroundStyle(OAKColor.text)
                    Text("Đang tải dữ liệu…")
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                        .foregroundStyle(OAKColor.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(18)
            .background(OAKColor.surface.opacity(0.96), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay { RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(OAKColor.border.opacity(0.8), lineWidth: 1) }
            .padding(.horizontal, 26)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(OAKColor.canvas.ignoresSafeArea())
    }
}
