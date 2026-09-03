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
        VStack(spacing: 14) {
            Image("OAKLogo")
                .resizable()
                .scaledToFit()
                .frame(width: 104, height: 104)
                .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            Text("OAK GATEKEEPER")
                .font(.system(size: 15, weight: .black, design: .monospaced))
                .foregroundStyle(OAKColor.text)
            ProgressView()
                .controlSize(.regular)
                .tint(OAKColor.accent)
            Text("Loading local H1…")
                .font(.system(size: 12, weight: .semibold, design: .rounded))
                .foregroundStyle(OAKColor.muted)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(OAKColor.canvas)
    }
}
