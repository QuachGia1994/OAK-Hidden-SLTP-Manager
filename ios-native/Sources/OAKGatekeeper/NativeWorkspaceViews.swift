import SwiftUI

@MainActor
struct NeoTechNativeView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                OAKPageHeader(
                    eyebrow: "OAK / NEOTECH",
                    title: "NeoTech",
                    subtitle: state.text(
                        vn: "C5 standalone · popup local + C5 LOOK · Telegram tùy chọn.",
                        en: "Standalone C5 · local popup + C5 LOOK · optional Telegram."
                    )
                )

                OAKCard(tint: OAKColor.accent) {
                    VStack(alignment: .leading, spacing: 13) {
                        HStack(alignment: .top, spacing: 12) {
                            ZStack {
                                Circle().stroke(OAKColor.accent.opacity(0.45), lineWidth: 1)
                                Circle().stroke(OAKColor.accent.opacity(0.75), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                                    .padding(8)
                                Text("C5")
                                    .font(.system(size: 17, weight: .black, design: .monospaced))
                                    .foregroundStyle(OAKColor.text)
                            }
                            .frame(width: 68, height: 68)

                            VStack(alignment: .leading, spacing: 5) {
                                OAKEyebrow(text: "VERSION 1.10 · STANDALONE")
                                Text(state.text(vn: "Cài một lần, chạy độc lập", en: "Install once, run standalone"))
                                    .font(.title2.bold())
                                    .foregroundStyle(OAKColor.text)
                                Text(state.text(
                                    vn: "EA tự bind tài khoản MT5. Không cần Node, PowerShell, bot token hay WebRequest để dùng cảnh báo C5 local.",
                                    en: "The EA auto-binds the active MT5 account. Local C5 alerts need no Node, PowerShell, bot token or WebRequest."
                                ))
                                .font(.footnote.weight(.medium))
                                .foregroundStyle(OAKColor.muted)
                                .fixedSize(horizontal: false, vertical: true)
                            }
                        }

                        HStack(spacing: 8) {
                            OAKPill(label: "C5 POPUP", tone: .success)
                            OAKPill(label: "C5 LOOK", tone: .accent)
                            OAKPill(label: "READ ONLY", tone: .muted)
                        }
                    }
                }

                if let accounts = state.payload?.accounts.accounts {
                    let mt5 = accounts.filter { $0.provider.lowercased() == "mt5" }
                    OAKCard {
                        VStack(alignment: .leading, spacing: 12) {
                            nativeSectionTitle(
                                state.text(vn: "MT5 ĐANG THEO DÕI", en: "MT5 MONITORING"),
                                meta: "\(mt5.count)"
                            )
                            if mt5.isEmpty {
                                Text(state.text(vn: "Chưa có account MT5 trong payload.", en: "No MT5 account is present in the payload yet."))
                                    .foregroundStyle(OAKColor.muted)
                            } else {
                                ForEach(mt5) { account in
                                    HStack(spacing: 10) {
                                        Circle()
                                            .fill(account.bridgeOnline == true ? OAKColor.success : OAKColor.warning)
                                            .frame(width: 8, height: 8)
                                            .accessibilityHidden(true)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(account.label)
                                                .font(.headline)
                                                .foregroundStyle(OAKColor.text)
                                            Text("\(account.broker) · \(account.traderLogin.map(String.init) ?? account.externalAccountId)")
                                                .font(.caption)
                                                .foregroundStyle(OAKColor.muted)
                                        }
                                        Spacer()
                                        OAKPill(
                                            label: account.bridgeOnline == true ? "ONLINE" : "WAIT",
                                            tone: account.bridgeOnline == true ? .success : .warning
                                        )
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            }
                        }
                    }
                }

                OAKCard {
                    VStack(alignment: .leading, spacing: 10) {
                        nativeSectionTitle(state.text(vn: "TELEGRAM", en: "TELEGRAM"), meta: state.text(vn: "Tùy chọn", en: "Optional"))
                        Text(state.text(
                            vn: "Nếu PC đã có OAK Local Telegram controller, reminder và /look được chuyển tiếp tự động. Không có Telegram thì C5 local vẫn hoạt động đầy đủ.",
                            en: "When the PC already runs the OAK Local Telegram controller, reminders and /look are forwarded automatically. Local C5 remains fully usable without Telegram."
                        ))
                        .font(.footnote)
                        .foregroundStyle(OAKColor.muted)
                        .fixedSize(horizontal: false, vertical: true)

                        Link(destination: URL(string: "https://www.oakgatekeeper.uk/neotech")!) {
                            Label(state.text(vn: "MỞ NEOTECH WEB", en: "OPEN NEOTECH WEB"), systemImage: "safari")
                                .font(.system(size: 12, weight: .black, design: .monospaced))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                        }
                        .buttonStyle(.glass)
                    }
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
        .navigationBarTitleDisplayMode(.inline)
    }
}

@MainActor
struct NativeToolsView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                OAKPageHeader(
                    eyebrow: "OAK / TOOLS",
                    title: state.text(vn: "Công cụ", en: "Tools"),
                    subtitle: state.text(
                        vn: "Một directory gọn cho tín hiệu, báo cáo, hệ thống và các công cụ OAK trên web.",
                        en: "A compact directory for signals, reports, system controls and OAK web tools."
                    )
                )

                nativeToolLink(
                    title: state.text(vn: "Tín hiệu", en: "Signals"),
                    detail: state.text(vn: "Radar BUY/SELL + drill-down bằng chứng signal", en: "BUY/SELL radar + signal-evidence drill-down"),
                    symbol: "waveform.path.ecg",
                    route: AppState.ToolsRoute.signals
                )

                nativeToolLink(
                    title: state.text(vn: "Báo cáo", en: "Reports"),
                    detail: state.text(vn: "Tóm tắt dữ liệu H1 đã lưu", en: "Summary of retained H1 data"),
                    symbol: "chart.bar.xaxis",
                    route: AppState.ToolsRoute.reports
                )

                nativeToolLink(
                    title: state.text(vn: "Hệ thống & tài khoản", en: "System & Accounts"),
                    detail: state.text(vn: "Theme, locale, provider heartbeat và account toggle", en: "Theme, locale, provider heartbeat and account toggles"),
                    symbol: "slider.horizontal.3",
                    route: AppState.ToolsRoute.system
                )

                OAKCard {
                    VStack(alignment: .leading, spacing: 10) {
                        nativeSectionTitle(state.text(vn: "WEB TOOLS", en: "WEB TOOLS"), meta: "oakgatekeeper.uk")
                        nativeWebLink(title: state.text(vn: "Xác thực ảnh AI", en: "Image authenticity"), path: "/factcheck", symbol: "checkmark.shield")
                        Divider()
                        nativeWebLink(title: "Tarot", path: "/tarot", symbol: "sparkles")
                        Divider()
                        nativeWebLink(title: "Discover", path: "/discover", symbol: "safari")
                    }
                }
            }
            .padding(16)
        }
        .background(OAKColor.canvas)
        .refreshable { await state.refresh() }
        .navigationBarTitleDisplayMode(.inline)
    }

    private func nativeToolLink(title: String, detail: String, symbol: String, route: AppState.ToolsRoute) -> some View {
        NavigationLink(value: route) {
            OAKCard {
                HStack(spacing: 13) {
                    Image(systemName: symbol)
                        .font(.system(size: 21, weight: .bold))
                        .foregroundStyle(OAKColor.accent)
                        .frame(width: 42, height: 42)
                        .background(OAKColor.accent.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title)
                            .font(.headline.bold())
                            .foregroundStyle(OAKColor.text)
                        Text(detail)
                            .font(.caption)
                            .foregroundStyle(OAKColor.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer()
                    Image(systemName: "arrow.up.right")
                        .foregroundStyle(OAKColor.accent)
                        .accessibilityHidden(true)
                }
                .accessibilityElement(children: .combine)
            }
        }
        .buttonStyle(.plain)
    }

    private func nativeWebLink(title: String, path: String, symbol: String) -> some View {
        Link(destination: URL(string: "https://www.oakgatekeeper.uk\(path)")!) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .foregroundStyle(OAKColor.accent)
                    .frame(width: 24)
                    .accessibilityHidden(true)
                Text(title)
                    .font(.headline)
                    .foregroundStyle(OAKColor.text)
                Spacer()
                Image(systemName: "arrow.up.right")
                    .foregroundStyle(OAKColor.muted)
                    .accessibilityHidden(true)
            }
            .padding(.vertical, 4)
            .accessibilityElement(children: .combine)
        }
    }
}

private func nativeSectionTitle(_ title: String, meta: String) -> some View {
    HStack {
        Text(title)
            .font(OAKFont.sectionTitle)
            .tracking(1)
            .foregroundStyle(OAKColor.text)
            .accessibilityAddTraits(.isHeader)
        Spacer()
        Text(meta)
            .font(.caption2.bold())
            .foregroundStyle(OAKColor.muted)
    }
}
