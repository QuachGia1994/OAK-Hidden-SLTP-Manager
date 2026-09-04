import Foundation

enum H1SignalSide: String, Codable, Sendable {
    case buy = "BUY"
    case sell = "SELL"
}

struct H1SampleBar: Codable, Sendable, Hashable {
    let brokerDate: String
    let brokerTime: String
    let hour: Int
    let minute: Int
    let direction: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let selected: Bool
}

struct H1SignalAlert: Codable, Sendable, Hashable, Identifiable {
    let slotHour: Int
    let symbol: String
    let profile: String
    let baseSymbol: String
    let baseSignal: H1SignalSide?
    let baseHour: Int?
    let baseMinute: Int?
    let baseDirection: String
    let signal: H1SignalSide?
    let scheduledSignal: H1SignalSide?
    let postSignalInverted: Bool?
    let postSignalRule: String?
    let entryHour: Int?
    let patternGroup: String?
    let patternFamily: String?
    let pattern: String?
    let scannerSource: String?
    let inversionBadge: Bool?
    let sampleBars: [H1SampleBar]?

    var id: String { "\(symbol):\(slotHour):\(entryHour ?? -1):\(pattern ?? "")" }
}

struct H1SymbolDay: Codable, Sendable {
    let alerts: [H1SignalAlert]
}

struct H1SignalDay: Codable, Sendable {
    let symbols: [String: H1SymbolDay]
}

struct H1SignalPayload: Codable, Sendable {
    let schemaVersion: Int
    let signalRuleVersion: Int?
    let profile: String
    let publishedAt: String
    let hours: [Int]
    let symbols: [String]
    let days: [String: H1SignalDay]
}

struct H1EvidenceFacts: Sendable, Hashable {
    let patternSource: String
    let rawBase: String
    let signalSource: String
    let rule: String
    let finalSignal: String
}

struct MobileSignalRow: Codable, Sendable, Hashable, Identifiable {
    let symbol: String
    let slotHour: Int
    let signal: H1SignalSide?
    let baseSignal: H1SignalSide?
    let baseDirection: String
    let postSignalInverted: Bool
    let postSignalRule: String

    var id: String { "\(symbol):\(slotHour):\(signal?.rawValue ?? "NONE")" }
}

struct MobileCalendarPayload: Codable, Sendable {
    let dates: [String]
    let historyDates: [String]
    let fallbackDates: [String]
    let latestDate: String
    let earliestDate: String
    let hasHistory: Bool
    let symbols: [String]
    let hours: [Int]
}

struct MobileSignalsPayload: Codable, Sendable {
    let brokerDate: String
    let today: [MobileSignalRow]
    let recent: [MobileSignalRow]
    let filters: [String]
}

struct MobileDashboardPayload: Codable, Sendable {
    let brokerDate: String
    let publishedAt: String?
    let latencyMs: Int
    let uptimePct: Double
    let status: String
    let totalSignals: Int
    let buySignals: Int
    let sellSignals: Int
    let vipUnlocked: Bool
    let providerOnline: Bool
    let today: [MobileSignalRow]
}

struct MobileReportTrend: Codable, Sendable, Identifiable {
    let date: String
    let value: Int
    let index: Int
    var id: Int { index }
}

struct MobileReportPayload: Codable, Sendable {
    let totalSignals: Int
    let buySignals: Int
    let sellSignals: Int
    let signalBalancePct: Double
    let trend: [MobileReportTrend]
}

struct MobileBridgeNode: Codable, Sendable, Identifiable {
    let id: String
    let label: String
    let online: Bool
}

struct MobileBridgePayload: Codable, Sendable {
    let brokerDate: String
    let mt5Online: Int
    let mt5Total: Int
    let ctraderEnabled: Int
    let ctraderTotal: Int
    let bridgeCells: [Int]
    let nodes: [MobileBridgeNode]
}

struct MobileSystemPayload: Codable, Sendable {
    struct H1: Codable, Sendable {
        let ready: Bool
        let schemaVersion: Int?
        let signalRuleVersion: Int?
        let profile: String?
        let publishedAt: String?
        let brokerDate: String
        let historyDays: Int
        let symbolCount: Int
        let blockCount: Int
    }

    struct ProviderSummary: Codable, Sendable {
        struct CTrader: Codable, Sendable {
            let connected: Bool
            let scope: String?
        }
        struct MT5: Codable, Sendable {
            let connected: Bool
            let onlineAccounts: Int
            let totalAccounts: Int
        }
        let ctrader: CTrader
        let mt5: MT5
    }

    struct AccountSummary: Codable, Sendable {
        let total: Int
        let enabled: Int
        let defaultAccountId: String
    }

    let payloadVersion: Int
    let serverTime: String
    let apiStatus: String
    let latencyMs: Int
    let h1: H1
    let providers: ProviderSummary
    let accounts: AccountSummary
}

struct AccountPayload: Codable, Sendable {
    struct Providers: Codable, Sendable {
        struct CTrader: Codable, Sendable {
            let connected: Bool
            let scope: String?
        }
        struct MT5: Codable, Sendable {
            let connected: Bool
            let mode: String
        }
        let ctrader: CTrader
        let mt5: MT5
    }

    let ok: Bool
    let providers: Providers
    let defaultAccountId: String
    let accounts: [ProviderAccount]
}

struct ProviderAccount: Codable, Sendable, Identifiable, Hashable {
    let id: String
    let provider: String
    let broker: String
    let environment: String
    let externalAccountId: String
    let traderLogin: Int?
    let label: String
    let enabled: Bool
    let isDefault: Bool
    let connectionMode: String
    let bridgeProfile: String?
    let fxSlPoints: Double?
    let fxTpPoints: Double?
    let goldSlPoints: Double?
    let goldTpPoints: Double?
    let bridgeOnline: Bool?
    let bridgeLastSeenAt: Double?
    let bridgeRuntime: String?
    let bridgeVersion: String?

    func withEnabled(_ nextEnabled: Bool) -> ProviderAccount {
        ProviderAccount(
            id: id,
            provider: provider,
            broker: broker,
            environment: environment,
            externalAccountId: externalAccountId,
            traderLogin: traderLogin,
            label: label,
            enabled: nextEnabled,
            isDefault: isDefault,
            connectionMode: connectionMode,
            bridgeProfile: bridgeProfile,
            fxSlPoints: fxSlPoints,
            fxTpPoints: fxTpPoints,
            goldSlPoints: goldSlPoints,
            goldTpPoints: goldTpPoints,
            bridgeOnline: bridgeOnline,
            bridgeLastSeenAt: bridgeLastSeenAt,
            bridgeRuntime: bridgeRuntime,
            bridgeVersion: bridgeVersion
        )
    }
}

struct MobileAppPayload: Codable, Sendable {
    let ok: Bool
    let h1: H1SignalPayload?
    let accounts: AccountPayload
    let calendar: MobileCalendarPayload
    let signals: MobileSignalsPayload
    let dashboard: MobileDashboardPayload
    let reports: MobileReportPayload
    let bridge: MobileBridgePayload
    let system: MobileSystemPayload
}

extension H1SignalPayload {
    var orderedDatesDescending: [String] { days.keys.sorted(by: >) }
    var latestDate: String { orderedDatesDescending.first ?? "" }

    func day(_ date: String) -> H1SignalDay? { days[date] }

    func alert(date: String, symbol: String, hour: Int) -> H1SignalAlert? {
        days[date]?.symbols[symbol]?.alerts.first(where: { $0.slotHour == hour })
    }

    func manualCloseH16(date: String) -> Bool {
        days[date]?.symbols["XAUUSD"]?.alerts.contains(where: { $0.slotHour == 3 && $0.entryHour == 4 }) == true
    }

    func evidenceFacts(date: String, sourceAlert: H1SignalAlert) -> H1EvidenceFacts {
        let baseHour = sourceAlert.baseHour.map { "H\(String(format: "%02d", $0))" } ?? "—"
        let baseSignal = sourceAlert.baseSignal?.rawValue ?? "—"
        let rawBase = sourceAlert.baseDirection.isEmpty
            ? "—"
            : "\(sourceAlert.baseSymbol.isEmpty ? "—" : sourceAlert.baseSymbol) PREV \(baseHour) · \(sourceAlert.baseDirection) → \(baseSignal)"
        var signalSource = ""
        var rule = "DIRECT BASE"

        if (sourceAlert.symbol == "GBPUSD" || sourceAlert.symbol == "EURUSD") && [9, 12, 14, 16].contains(sourceAlert.slotHour) {
            let xau = alert(date: date, symbol: "XAUUSD", hour: sourceAlert.slotHour)
            signalSource = "XAUUSD H\(String(format: "%02d", sourceAlert.slotHour)) · \(xau?.signal?.rawValue ?? "—")"
            rule = "SYNC XAUUSD"
        } else if sourceAlert.slotHour == 16 {
            let h14 = alert(date: date, symbol: sourceAlert.symbol, hour: 14)
            let xauH3Entry = alert(date: date, symbol: "XAUUSD", hour: 3)?.entryHour
            signalSource = "\(sourceAlert.symbol) H14 · \(h14?.signal?.rawValue ?? "—")"
            rule = xauH3Entry == 4 ? "INVERT H14" : xauH3Entry == 5 ? "COPY H14" : "H14 OVERRIDE"
        }

        return H1EvidenceFacts(
            patternSource: sourceAlert.scannerSource ?? sourceAlert.symbol,
            rawBase: rawBase,
            signalSource: signalSource,
            rule: rule,
            finalSignal: sourceAlert.signal?.rawValue ?? "—"
        )
    }

    func alerts(date: String, visibleSymbols: [String]) -> [H1SignalAlert] {
        visibleSymbols.flatMap { symbol in
            days[date]?.symbols[symbol]?.alerts ?? []
        }
        .sorted { lhs, rhs in
            if lhs.slotHour != rhs.slotHour { return lhs.slotHour < rhs.slotHour }
            return lhs.symbol < rhs.symbol
        }
    }
}
