import SwiftUI

@MainActor
struct MainTabView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        @Bindable var state = state
        TabView(selection: $state.selectedTab) {
            Tab(state.text(vn: "Live", en: "Live"), systemImage: "waveform.path.ecg", value: AppState.Tab.live) {
                NavigationStack { H1BoardScreen(mode: .live) }
            }

            Tab(state.text(vn: "Lịch sử", en: "History"), systemImage: "calendar", value: AppState.Tab.history) {
                NavigationStack { H1BoardScreen(mode: .history) }
            }

            Tab(state.text(vn: "Tín hiệu", en: "Signals"), systemImage: "bolt.horizontal.fill", value: AppState.Tab.signals) {
                NavigationStack { SignalsView() }
            }

            Tab(state.text(vn: "Báo cáo", en: "Reports"), systemImage: "chart.bar.xaxis", value: AppState.Tab.reports) {
                NavigationStack { ReportsView() }
            }

            Tab(state.text(vn: "Thêm", en: "More"), systemImage: "ellipsis.circle", value: AppState.Tab.more) {
                NavigationStack { MoreView() }
            }
        }
        .tabBarMinimizeBehavior(.onScrollDown)
        .tint(OAKColor.accent)
    }
}
