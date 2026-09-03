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
        let previous = payload
        applyAccountEnabledLocally(id: id, enabled: enabled)
        do {
            let accounts = try await api.setAccountEnabled(apiKey: apiKey, id: id, enabled: enabled)
            applyAccountSnapshot(accounts)
            errorMessage = ""
            Task { @MainActor [weak self] in
                await self?.refresh()
            }
        } catch {
            payload = previous
            errorMessage = error.localizedDescription
        }
    }

    private func applyAccountEnabledLocally(id: String, enabled: Bool) {
        guard let current = payload else { return }
        let nextAccounts = current.accounts.accounts.map { account in
            account.id == id ? account.withEnabled(enabled) : account
        }
        let snapshot = AccountPayload(
            ok: current.accounts.ok,
            providers: current.accounts.providers,
            defaultAccountId: current.accounts.defaultAccountId,
            accounts: nextAccounts
        )
        applyAccountSnapshot(snapshot)
    }

    private func applyAccountSnapshot(_ accounts: AccountPayload) {
        guard let current = payload else { return }
        let enabledCount = accounts.accounts.filter(\.enabled).count
        let system = MobileSystemPayload(
            payloadVersion: current.system.payloadVersion,
            serverTime: current.system.serverTime,
            apiStatus: current.system.apiStatus,
            latencyMs: current.system.latencyMs,
            h1: current.system.h1,
            providers: current.system.providers,
            accounts: MobileSystemPayload.AccountSummary(
                total: accounts.accounts.count,
                enabled: enabledCount,
                defaultAccountId: accounts.defaultAccountId
            )
        )
        payload = MobileAppPayload(
            ok: current.ok,
            h1: current.h1,
            accounts: accounts,
            calendar: current.calendar,
            signals: current.signals,
            dashboard: current.dashboard,
            reports: current.reports,
            bridge: current.bridge,
            system: system
        )
    }
}
