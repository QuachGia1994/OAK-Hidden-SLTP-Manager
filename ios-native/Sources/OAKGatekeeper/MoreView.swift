import SwiftUI

@MainActor
struct MoreView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                OAKPageHeader(
                    eyebrow: "OAK / SYSTEM",
                    title: state.text(vn: "Hệ thống", en: "System"),
                    subtitle: state.text(vn: "Trạng thái backend, H1 feed, providers và account routing.", en: "Backend, H1 feed, provider and account-routing status.")
                )

                appearanceCard

                if let system = state.payload?.system {
                    OAKCard(tint: system.h1.ready ? OAKColor.success : OAKColor.warning) {
                        VStack(alignment: .leading, spacing: 13) {
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text("OAK Gatekeeper Native")
                                        .font(.headline.bold())
                                        .foregroundStyle(OAKColor.text)
                                    Text("SwiftUI · Xcode 27 · iOS 27 SDK")
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(OAKColor.muted)
                                }
                                Spacer()
                                OAKPill(label: system.apiStatus, tone: .success)
                            }
                            HStack(spacing: 8) {
                                OAKMetric(label: "API LATENCY", value: "\(system.latencyMs)ms", valueColor: OAKColor.accent)
                                OAKMetric(label: "H1 FEED", value: system.h1.ready ? "READY" : "WAIT", valueColor: system.h1.ready ? OAKColor.success : OAKColor.warning)
                            }
                        }
                    }

                    OAKCard {
                        VStack(alignment: .leading, spacing: 13) {
                            sectionTitle("H1 FEED", meta: system.h1.brokerDate)
                            HStack(spacing: 8) {
                                OAKMetric(label: "SCHEMA", value: "v\(system.h1.schemaVersion ?? 0)")
                                OAKMetric(label: "RULE", value: "v\(system.h1.signalRuleVersion ?? 0)")
                                OAKMetric(label: "HISTORY", value: "\(system.h1.historyDays) days", valueColor: OAKColor.accent)
                                OAKMetric(label: "SYMBOLS/BLOCKS", value: "\(system.h1.symbolCount) / \(system.h1.blockCount)")
                            }
                            Divider()
                            Text(system.h1.profile ?? "—")
                                .font(.system(size: 12, weight: .bold, design: .monospaced))
                                .foregroundStyle(OAKColor.text)
                        }
                    }

                    OAKCard {
                        VStack(alignment: .leading, spacing: 12) {
                            sectionTitle("PROVIDERS", meta: "\(system.accounts.enabled)/\(system.accounts.total) enabled")
                            providerRow(name: "cTrader", detail: "Scope: \(system.providers.ctrader.scope ?? "—")", online: system.providers.ctrader.connected)
                            Divider()
                            providerRow(name: "MT5", detail: "\(system.providers.mt5.onlineAccounts)/\(system.providers.mt5.totalAccounts) bridge online", online: system.providers.mt5.connected)
                        }
                    }
                }

                if let accounts = state.payload?.accounts.accounts {
                    OAKCard {
                        VStack(alignment: .leading, spacing: 12) {
                            sectionTitle("ACCOUNTS", meta: "\(accounts.count) total")
                            ForEach(accounts) { account in
                                accountRow(account)
                                if account.id != accounts.last?.id { Divider() }
                            }
                        }
                    }
                }

                OAKCard {
                    VStack(spacing: 10) {
                        Link(destination: URL(string: "https://www.oakgatekeeper.uk")!) {
                            Label(state.text(vn: "MỞ WEB", en: "OPEN WEB"), systemImage: "safari")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                        }
                        .buttonStyle(.glass)

                        Button(role: .destructive) { state.signOut() } label: {
                            Label(state.text(vn: "ĐĂNG XUẤT", en: "SIGN OUT"), systemImage: "rectangle.portrait.and.arrow.right")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                        }
                        .buttonStyle(.glass)
                    }
                }

                if !state.errorMessage.isEmpty {
                    Text(state.errorMessage)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(OAKColor.danger)
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
    }

    private var appearanceCard: some View {
        OAKCard {
            VStack(alignment: .leading, spacing: 13) {
                sectionTitle(state.text(vn: "GIAO DIỆN", en: "APPEARANCE"), meta: "native")
                Text(state.text(vn: "Theme", en: "Theme"))
                    .font(.caption.bold())
                    .foregroundStyle(OAKColor.muted)
                Picker("Theme", selection: Binding(
                    get: { state.themeMode },
                    set: { state.setTheme($0) }
                )) {
                    Text("Light").tag(OAKThemeMode.light)
                    Text("Dark").tag(OAKThemeMode.dark)
                    Text("Contrast").tag(OAKThemeMode.contrast)
                }
                .pickerStyle(.segmented)

                Text(state.text(vn: "Ngôn ngữ", en: "Language"))
                    .font(.caption.bold())
                    .foregroundStyle(OAKColor.muted)
                Picker("Locale", selection: Binding(
                    get: { state.locale },
                    set: { state.setLocale($0) }
                )) {
                    Text("VN").tag(OAKLocale.vn)
                    Text("EN").tag(OAKLocale.en)
                }
                .pickerStyle(.segmented)
            }
        }
    }

    private func sectionTitle(_ title: String, meta: String) -> some View {
        HStack {
            Text(title)
                .font(.system(size: 12, weight: .black, design: .monospaced))
                .tracking(1)
                .foregroundStyle(OAKColor.text)
            Spacer()
            Text(meta)
                .font(.caption2.bold())
                .foregroundStyle(OAKColor.muted)
        }
    }

    private func providerRow(name: String, detail: String, online: Bool) -> some View {
        HStack(spacing: 11) {
            Circle()
                .fill(online ? OAKColor.success : OAKColor.warning)
                .frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 3) {
                Text(name).font(.headline).foregroundStyle(OAKColor.text)
                Text(detail).font(.caption).foregroundStyle(OAKColor.muted)
            }
            Spacer()
            OAKPill(label: online ? "ONLINE" : "OFFLINE", tone: online ? .success : .warning)
        }
    }

    private func accountRow(_ account: ProviderAccount) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 7) {
                    Text(account.label)
                        .font(.headline)
                        .foregroundStyle(OAKColor.text)
                    if account.isDefault { OAKPill(label: "DEFAULT", tone: .accent) }
                }
                Text("\(account.provider.uppercased()) · \(account.broker) · \(account.traderLogin.map(String.init) ?? account.externalAccountId)")
                    .font(.caption)
                    .foregroundStyle(OAKColor.muted)
                if account.provider == "mt5" {
                    Text(account.bridgeOnline == true ? "Bridge online" : "Bridge offline")
                        .font(.caption2.bold())
                        .foregroundStyle(account.bridgeOnline == true ? OAKColor.success : OAKColor.warning)
                }
            }
            Spacer()
            Toggle("", isOn: Binding(
                get: {
                    state.payload?.accounts.accounts.first(where: { $0.id == account.id })?.enabled ?? account.enabled
                },
                set: { enabled in Task { await state.toggleAccount(id: account.id, enabled: enabled) } }
            ))
            .labelsHidden()
        }
    }
}
