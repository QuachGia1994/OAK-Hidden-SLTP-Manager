import Foundation
import Observation

@MainActor
@Observable
final class AppState {
    enum Tab: Hashable, Sendable {
        case live, history, signals, reports, more
    }

    var selectedTab: Tab = .live
    var apiKey: String
    var payload: MobileAppPayload?
    var isLoading = false
    var isRefreshing = false
    var errorMessage = ""
    var lastRefreshAt: Date?
    var themeMode: OAKThemeMode
    var locale: OAKLocale

    private let api = OAKAPIClient()

    init() {
        apiKey = KeychainStore.readAPIKey()
        themeMode = OAKThemeMode(rawValue: UserDefaults.standard.string(forKey: "oak.theme") ?? "light") ?? .light
        locale = OAKLocale(rawValue: UserDefaults.standard.string(forKey: "oak.locale") ?? "VN") ?? .vn
    }

    var isUnlocked: Bool { !apiKey.isEmpty }

    func text(vn: String, en: String) -> String {
        locale == .vn ? vn : en
    }

    func setTheme(_ next: OAKThemeMode) {
        themeMode = next
        UserDefaults.standard.set(next.rawValue, forKey: "oak.theme")
    }

    func setLocale(_ next: OAKLocale) {
        locale = next
        UserDefaults.standard.set(next.rawValue, forKey: "oak.locale")
    }

    func unlock(candidate: String) async throws {
        let key = candidate.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { throw OAKAPIError.unauthorized }
        _ = try await api.fetchAccounts(apiKey: key)
        try KeychainStore.writeAPIKey(key)
        apiKey = key
        errorMessage = ""
        await refresh(forceLoading: true)
    }

    func signOut() {
        do { try KeychainStore.deleteAPIKey() } catch { errorMessage = error.localizedDescription }
        apiKey = ""
        payload = nil
        selectedTab = .live
    }

    func refresh(forceLoading: Bool = false) async {
        guard isUnlocked else { return }
        if forceLoading || payload == nil { isLoading = true }
        isRefreshing = true
        defer {
            isLoading = false
            isRefreshing = false
        }
        do {
            payload = try await api.fetchApp(apiKey: apiKey)
            errorMessage = ""
            lastRefreshAt = Date()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refreshLoop() async {
        await refresh(forceLoading: payload == nil)
        while !Task.isCancelled {
            do { try await Task.sleep(for: .seconds(20)) } catch { return }
            await refresh()
        }
    }

    func toggleAccount(id: String, enabled: Bool) async {
        guard isUnlocked else { return }
        do {
            let accounts = try await api.setAccountEnabled(apiKey: apiKey, id: id, enabled: enabled)
            if let current = payload {
                payload = MobileAppPayload(
                    ok: current.ok,
                    h1: current.h1,
                    accounts: accounts,
                    calendar: current.calendar,
                    signals: current.signals,
                    dashboard: current.dashboard,
                    reports: current.reports,
                    bridge: current.bridge,
                    system: current.system
                )
            }
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
