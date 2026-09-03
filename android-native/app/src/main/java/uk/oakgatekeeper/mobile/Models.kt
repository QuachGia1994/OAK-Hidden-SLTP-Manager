package uk.oakgatekeeper.mobile

import org.json.JSONArray
import org.json.JSONObject

enum class SignalSide { BUY, SELL }

data class H1SampleBar(
    val brokerDate: String,
    val brokerTime: String,
    val hour: Int,
    val minute: Int,
    val direction: String,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val selected: Boolean,
)

data class H1SignalAlert(
    val slotHour: Int,
    val symbol: String,
    val profile: String,
    val baseSymbol: String,
    val baseSignal: SignalSide?,
    val baseHour: Int?,
    val baseMinute: Int?,
    val baseDirection: String,
    val signal: SignalSide?,
    val scheduledSignal: SignalSide?,
    val postSignalInverted: Boolean,
    val postSignalRule: String,
    val entryHour: Int?,
    val patternGroup: String?,
    val patternFamily: String?,
    val pattern: String?,
    val scannerSource: String?,
    val inversionBadge: Boolean,
    val sampleBars: List<H1SampleBar>,
) {
    val id: String get() = "$symbol:$slotHour:${entryHour ?: -1}:${pattern.orEmpty()}"
}

data class H1SymbolDay(val alerts: List<H1SignalAlert>)
data class H1SignalDay(val symbols: Map<String, H1SymbolDay>)

data class H1SignalPayload(
    val schemaVersion: Int,
    val signalRuleVersion: Int,
    val profile: String,
    val publishedAt: String,
    val hours: List<Int>,
    val symbols: List<String>,
    val days: Map<String, H1SignalDay>,
) {
    val orderedDatesDescending: List<String> get() = days.keys.sortedDescending()
    val latestDate: String get() = orderedDatesDescending.firstOrNull().orEmpty()

    fun alert(date: String, symbol: String, hour: Int): H1SignalAlert? =
        days[date]?.symbols?.get(symbol)?.alerts?.firstOrNull { it.slotHour == hour }

    fun manualCloseH16(date: String): Boolean =
        days[date]?.symbols?.get("XAUUSD")?.alerts?.any { it.slotHour == 3 && it.entryHour == 5 } == true

    fun alerts(date: String, visibleSymbols: List<String>): List<H1SignalAlert> =
        visibleSymbols.flatMap { days[date]?.symbols?.get(it)?.alerts.orEmpty() }
            .sortedWith(compareBy<H1SignalAlert> { it.slotHour }.thenBy { it.symbol })
}

data class ReportTrend(val date: String, val value: Int, val index: Int)
data class ReportsPayload(
    val totalSignals: Int,
    val buySignals: Int,
    val sellSignals: Int,
    val signalBalancePct: Double,
    val trend: List<ReportTrend>,
)

data class SystemH1(
    val ready: Boolean,
    val schemaVersion: Int,
    val signalRuleVersion: Int,
    val profile: String,
    val publishedAt: String,
    val brokerDate: String,
    val historyDays: Int,
    val symbolCount: Int,
    val blockCount: Int,
)

data class ProviderSummary(
    val ctraderConnected: Boolean,
    val ctraderScope: String,
    val mt5Connected: Boolean,
    val mt5OnlineAccounts: Int,
    val mt5TotalAccounts: Int,
)

data class AccountSummary(val total: Int, val enabled: Int, val defaultAccountId: String)

data class SystemPayload(
    val payloadVersion: Int,
    val serverTime: String,
    val apiStatus: String,
    val latencyMs: Int,
    val h1: SystemH1,
    val providers: ProviderSummary,
    val accounts: AccountSummary,
)

data class ProviderAccount(
    val id: String,
    val provider: String,
    val broker: String,
    val environment: String,
    val externalAccountId: String,
    val traderLogin: Int?,
    val label: String,
    val enabled: Boolean,
    val isDefault: Boolean,
    val connectionMode: String,
    val bridgeProfile: String?,
    val bridgeOnline: Boolean?,
    val bridgeRuntime: String?,
    val bridgeVersion: String?,
) {
    fun withEnabled(next: Boolean) = copy(enabled = next)
}

data class AccountsPayload(
    val ok: Boolean,
    val defaultAccountId: String,
    val accounts: List<ProviderAccount>,
)

data class MobileAppPayload(
    val ok: Boolean,
    val h1: H1SignalPayload?,
    val accounts: AccountsPayload,
    val reports: ReportsPayload,
    val system: SystemPayload,
)

object OAKJson {
    fun app(raw: String): MobileAppPayload {
        val root = JSONObject(raw)
        return MobileAppPayload(
            ok = root.optBoolean("ok", false),
            h1 = root.optJSONObject("h1")?.let(::h1),
            accounts = accounts(root.getJSONObject("accounts")),
            reports = reports(root.getJSONObject("reports")),
            system = system(root.getJSONObject("system")),
        )
    }

    fun accountsEnvelope(raw: String): AccountsPayload {
        val root = JSONObject(raw)
        val payload = root.optJSONObject("payload") ?: root
        return accounts(payload)
    }

    private fun h1(obj: JSONObject): H1SignalPayload {
        val dayMap = linkedMapOf<String, H1SignalDay>()
        val days = obj.optJSONObject("days") ?: JSONObject()
        for (date in days.keys()) {
            val day = days.optJSONObject(date) ?: continue
            val symbols = day.optJSONObject("symbols") ?: JSONObject()
            val symbolMap = linkedMapOf<String, H1SymbolDay>()
            for (symbol in symbols.keys()) {
                val symbolDay = symbols.optJSONObject(symbol) ?: continue
                val alerts = symbolDay.optJSONArray("alerts") ?: JSONArray()
                symbolMap[symbol] = H1SymbolDay(alerts.toAlertList())
            }
            dayMap[date] = H1SignalDay(symbolMap)
        }
        return H1SignalPayload(
            schemaVersion = obj.optInt("schemaVersion", 0),
            signalRuleVersion = obj.optInt("signalRuleVersion", 0),
            profile = obj.optString("profile", ""),
            publishedAt = obj.optString("publishedAt", ""),
            hours = obj.optJSONArray("hours").toIntList(),
            symbols = obj.optJSONArray("symbols").toStringList(),
            days = dayMap,
        )
    }

    private fun JSONArray.toAlertList(): List<H1SignalAlert> = buildList {
        for (index in 0 until length()) {
            val obj = optJSONObject(index) ?: continue
            add(
                H1SignalAlert(
                    slotHour = obj.optInt("slotHour", 0),
                    symbol = obj.optString("symbol", ""),
                    profile = obj.optString("profile", ""),
                    baseSymbol = obj.optString("baseSymbol", ""),
                    baseSignal = obj.optSignal("baseSignal"),
                    baseHour = obj.optIntOrNull("baseHour"),
                    baseMinute = obj.optIntOrNull("baseMinute"),
                    baseDirection = obj.optString("baseDirection", ""),
                    signal = obj.optSignal("signal"),
                    scheduledSignal = obj.optSignal("scheduledSignal"),
                    postSignalInverted = obj.optBoolean("postSignalInverted", false),
                    postSignalRule = obj.optString("postSignalRule", "none"),
                    entryHour = obj.optIntOrNull("entryHour"),
                    patternGroup = obj.optStringOrNull("patternGroup"),
                    patternFamily = obj.optStringOrNull("patternFamily"),
                    pattern = obj.optStringOrNull("pattern"),
                    scannerSource = obj.optStringOrNull("scannerSource"),
                    inversionBadge = obj.optBoolean("inversionBadge", false),
                    sampleBars = obj.optJSONArray("sampleBars").toSampleBars(),
                )
            )
        }
    }

    private fun JSONArray?.toSampleBars(): List<H1SampleBar> {
        if (this == null) return emptyList()
        return buildList {
            for (index in 0 until length()) {
                val obj = optJSONObject(index) ?: continue
                add(
                    H1SampleBar(
                        brokerDate = obj.optString("brokerDate", ""),
                        brokerTime = obj.optString("brokerTime", ""),
                        hour = obj.optInt("hour", 0),
                        minute = obj.optInt("minute", 0),
                        direction = obj.optString("direction", ""),
                        open = obj.optDouble("open", 0.0),
                        high = obj.optDouble("high", 0.0),
                        low = obj.optDouble("low", 0.0),
                        close = obj.optDouble("close", 0.0),
                        selected = obj.optBoolean("selected", false),
                    )
                )
            }
        }
    }

    private fun accounts(obj: JSONObject): AccountsPayload {
        val list = obj.optJSONArray("accounts") ?: JSONArray()
        val rows = buildList {
            for (index in 0 until list.length()) {
                val account = list.optJSONObject(index) ?: continue
                add(
                    ProviderAccount(
                        id = account.optString("id", ""),
                        provider = account.optString("provider", ""),
                        broker = account.optString("broker", ""),
                        environment = account.optString("environment", ""),
                        externalAccountId = account.optString("externalAccountId", ""),
                        traderLogin = account.optIntOrNull("traderLogin"),
                        label = account.optString("label", ""),
                        enabled = account.optBoolean("enabled", false),
                        isDefault = account.optBoolean("isDefault", false),
                        connectionMode = account.optString("connectionMode", ""),
                        bridgeProfile = account.optStringOrNull("bridgeProfile"),
                        bridgeOnline = account.optBooleanOrNull("bridgeOnline"),
                        bridgeRuntime = account.optStringOrNull("bridgeRuntime"),
                        bridgeVersion = account.optStringOrNull("bridgeVersion"),
                    )
                )
            }
        }
        return AccountsPayload(
            ok = obj.optBoolean("ok", true),
            defaultAccountId = obj.optString("defaultAccountId", ""),
            accounts = rows,
        )
    }

    private fun reports(obj: JSONObject): ReportsPayload {
        val trend = obj.optJSONArray("trend") ?: JSONArray()
        val rows = buildList {
            for (index in 0 until trend.length()) {
                val point = trend.optJSONObject(index) ?: continue
                add(ReportTrend(point.optString("date", ""), point.optInt("value", 0), point.optInt("index", index)))
            }
        }
        return ReportsPayload(
            totalSignals = obj.optInt("totalSignals", 0),
            buySignals = obj.optInt("buySignals", 0),
            sellSignals = obj.optInt("sellSignals", 0),
            signalBalancePct = obj.optDouble("signalBalancePct", 0.0),
            trend = rows,
        )
    }

    private fun system(obj: JSONObject): SystemPayload {
        val h1 = obj.optJSONObject("h1") ?: JSONObject()
        val providers = obj.optJSONObject("providers") ?: JSONObject()
        val ctrader = providers.optJSONObject("ctrader") ?: JSONObject()
        val mt5 = providers.optJSONObject("mt5") ?: JSONObject()
        val accounts = obj.optJSONObject("accounts") ?: JSONObject()
        return SystemPayload(
            payloadVersion = obj.optInt("payloadVersion", 0),
            serverTime = obj.optString("serverTime", ""),
            apiStatus = obj.optString("apiStatus", "OFFLINE"),
            latencyMs = obj.optInt("latencyMs", 0),
            h1 = SystemH1(
                ready = h1.optBoolean("ready", false),
                schemaVersion = h1.optInt("schemaVersion", 0),
                signalRuleVersion = h1.optInt("signalRuleVersion", 0),
                profile = h1.optString("profile", ""),
                publishedAt = h1.optString("publishedAt", ""),
                brokerDate = h1.optString("brokerDate", ""),
                historyDays = h1.optInt("historyDays", 0),
                symbolCount = h1.optInt("symbolCount", 0),
                blockCount = h1.optInt("blockCount", 0),
            ),
            providers = ProviderSummary(
                ctraderConnected = ctrader.optBoolean("connected", false),
                ctraderScope = ctrader.optString("scope", "—"),
                mt5Connected = mt5.optBoolean("connected", false),
                mt5OnlineAccounts = mt5.optInt("onlineAccounts", 0),
                mt5TotalAccounts = mt5.optInt("totalAccounts", 0),
            ),
            accounts = AccountSummary(
                total = accounts.optInt("total", 0),
                enabled = accounts.optInt("enabled", 0),
                defaultAccountId = accounts.optString("defaultAccountId", ""),
            ),
        )
    }

    private fun JSONObject.optSignal(name: String): SignalSide? = when (optString(name, "").uppercase()) {
        "BUY" -> SignalSide.BUY
        "SELL" -> SignalSide.SELL
        else -> null
    }

    private fun JSONObject.optIntOrNull(name: String): Int? =
        if (!has(name) || isNull(name)) null else optInt(name)

    private fun JSONObject.optBooleanOrNull(name: String): Boolean? =
        if (!has(name) || isNull(name)) null else optBoolean(name)

    private fun JSONObject.optStringOrNull(name: String): String? =
        if (!has(name) || isNull(name)) null else optString(name).takeIf { it.isNotBlank() }

    private fun JSONArray?.toIntList(): List<Int> {
        if (this == null) return emptyList()
        return buildList { for (index in 0 until length()) add(optInt(index)) }
    }

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return buildList { for (index in 0 until length()) add(optString(index)) }
    }
}
