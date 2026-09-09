import SwiftUI

@MainActor
struct MainTabView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        @Bindable var state = state
        TabView(selection: $state.selectedTab) {
            Tab(state.text(vn: "H1 Live", en: "H1 Live"), systemImage: "chart.xyaxis.line", value: AppState.Tab.live) {
                NavigationStack { H1BoardScreen(mode: .live) }
            }

            Tab(state.text(vn: "NeoTech", en: "NeoTech"), systemImage: "scope", value: AppState.Tab.neotech) {
                NavigationStack { NeoTechNativeView() }
            }

            Tab(state.text(vn: "Công cụ", en: "Tools"), systemImage: "slider.horizontal.3", value: AppState.Tab.tools) {
                NavigationStack { NativeToolsView() }
            }
        }
        .tabBarMinimizeBehavior(.onScrollDown)
        .tint(OAKColor.accent)
    }
}
