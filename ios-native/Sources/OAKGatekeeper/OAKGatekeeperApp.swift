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
                MainTabView()
                    .task(id: state.apiKey) { await state.refreshLoop() }
            } else {
                UnlockView()
            }
        }
        .background(OAKColor.canvas.ignoresSafeArea())
    }
}
