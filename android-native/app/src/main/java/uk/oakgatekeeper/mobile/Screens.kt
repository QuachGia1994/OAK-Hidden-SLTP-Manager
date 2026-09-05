@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package uk.oakgatekeeper.mobile

import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale
import kotlinx.coroutines.delay
import kotlin.math.max

private val VisibleSymbols = listOf("XAUUSD", "GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY")

@Composable
fun UnlockScreen(state: OAKAppState) {
    val p = LocalOAKPalette.current
    var key by remember { mutableStateOf("") }

    Box(Modifier.fillMaxSize().background(p.canvas)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            item { Spacer(Modifier.height(38.dp)) }
            item {
                OAKPageHeader(
                    eyebrow = "OAK / MOBILE",
                    title = "OAK Gatekeeper",
                    subtitle = state.text(
                        "Ứng dụng native Android cho ROBOT SLTP · dữ liệu H1 lấy trực tiếp từ backend.",
                        "Native Android client for ROBOT SLTP · H1 data comes directly from the backend.",
                    ),
                )
            }
            item {
                OAKCard(tint = p.accent) {
                    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        OAKEyebrow("SECURE ACCESS")
                        Text(state.text("Mở khóa dashboard", "Unlock dashboard"), color = p.text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                        OutlinedTextField(
                            value = key,
                            onValueChange = { key = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Dashboard API key") },
                            singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(autoCorrectEnabled = false),
                        )
                        Button(
                            onClick = { state.unlock(key) },
                            enabled = key.trim().isNotEmpty() && !state.isUnlocking,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            if (state.isUnlocking) CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            if (state.isUnlocking) Spacer(Modifier.width(8.dp))
                            Text(state.text("MỞ KHÓA", "UNLOCK"), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
                        }
                        if (state.unlockError.isNotBlank()) {
                            Text(state.unlockError, color = p.danger, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                        Text(
                            state.text(
                                "API key được mã hóa bằng Android Keystore và không nhúng vào binary.",
                                "The API key is encrypted with Android Keystore and is never embedded in the binary.",
                            ),
                            color = p.muted,
                            fontSize = 13.sp,
                            lineHeight = 19.sp,
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun H1BoardScreen(state: OAKAppState, history: Boolean) {
    val p = LocalOAKPalette.current
    val context = LocalContext.current
    val h1 = state.payload?.h1
    var selectedDate by remember(h1?.latestDate) { mutableStateOf(h1?.latestDate.orEmpty()) }
    var selectedAlert by remember { mutableStateOf<H1SignalAlert?>(null) }
    var calendarOpen by remember { mutableStateOf(false) }
    var copiedSchedule by remember(h1?.latestDate, history, selectedDate) { mutableStateOf(false) }
    LaunchedEffect(copiedSchedule) {
        if (copiedSchedule) {
            delay(1_400)
            copiedSchedule = false
        }
    }
    if (!history && h1 != null && selectedDate != h1.latestDate) selectedDate = h1.latestDate
    if (history && h1 != null && (selectedDate.isBlank() || h1.days[selectedDate] == null)) selectedDate = h1.latestDate

    val date = if (history) selectedDate else h1?.latestDate.orEmpty()

    OAKScreen(
        state = state,
        eyebrow = if (history) "TRADING / HISTORY" else "TRADING / H1 LIVE",
        title = if (history) state.text("Lịch sử H1", "H1 History") else "H1 Live",
        subtitle = if (history) state.text(
            "Xem lại các ngày broker đã lưu mà không cần quay về màn hình live.",
            "Review retained broker days without returning to the live screen.",
        ) else state.text(
            "Ngày broker hiện tại · entry pattern M15 ICMarkets local",
            "Current broker day · local ICMarkets M15 pattern entries",
        ),
    ) {
        if (h1 != null && date.isNotBlank()) {
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(13.dp)) {
                        Row(verticalAlignment = Alignment.Top) {
                            Column {
                                OAKEyebrow(if (history) "H1 / HISTORY" else "H1 / LIVE")
                                Text(state.text("Lịch block H1", "H1 Block Schedule"), color = p.text, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.weight(1f))
                            Column(horizontalAlignment = Alignment.End) {
                                TextButton(
                                    onClick = {
                                        val copied = ShareStore.copyScheduleToClipboard(context, h1, date, VisibleSymbols)
                                        copiedSchedule = copied
                                        Toast.makeText(
                                            context,
                                            if (copied) state.text("Đã copy PNG · có thể dán sang Telegram", "PNG copied · ready to paste in Telegram")
                                            else state.text("Không thể copy PNG", "Unable to copy PNG"),
                                            Toast.LENGTH_SHORT,
                                        ).show()
                                    },
                                ) {
                                    Text(if (copiedSchedule) "✓ COPIED" else "COPY PNG", color = p.accent, fontSize = 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                                }
                                TextButton(
                                    onClick = {
                                        if (!ShareStore.shareSchedule(context, h1, date, VisibleSymbols)) {
                                            Toast.makeText(context, state.text("Không thể mở chia sẻ PNG", "Unable to open PNG sharing"), Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                ) {
                                    Text("SHARE PNG", color = p.accent, fontSize = 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                                }
                            }
                        }
                        Row(Modifier.fillMaxWidth()) {
                            OAKMetric("BROKER DAY", date, modifier = Modifier.weight(1f))
                            MetricDivider()
                            OAKMetric("UPDATED", shortPublished(h1.publishedAt), modifier = Modifier.weight(1f))
                        }
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OAKPill("FREE ACCESS", PillTone.SUCCESS)
                            Text(state.text("Tất cả ô entry-time H1 đã được mở", "All H1 entry-time cells unlocked"), color = p.muted, fontSize = 13.sp, modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
            if (history) {
                item {
                    OAKCard {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text(state.text("NGÀY BROKER", "BROKER DATE"), color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(p.raised, RoundedCornerShape(14.dp))
                                    .border(1.dp, p.border, RoundedCornerShape(14.dp))
                                    .clickable { calendarOpen = true }
                                    .padding(13.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(Icons.Default.DateRange, contentDescription = null, tint = p.accent, modifier = Modifier.size(20.dp))
                                Spacer(Modifier.width(10.dp))
                                Text(displayDate(date), color = p.text, fontSize = 17.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                                Spacer(Modifier.weight(1f))
                                Text("▾", color = p.muted)
                            }
                            Text("${h1.orderedDatesDescending.size} ${state.text("ngày giao dịch", "trading days")} · ${h1.orderedDatesDescending.lastOrNull() ?: "—"} → ${h1.latestDate}", color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }
            item { H1Matrix(h1, date, onSelect = { selectedAlert = it }) }
        } else {
            item {
                OAKCard(tint = p.warning) {
                    Text(if (state.isLoading) state.text("Đang tải H1…", "Loading H1…") else state.text("Đang chờ feed H1 local.", "Awaiting the local H1 feed."), color = p.muted)
                }
            }
        }
    }

    if (calendarOpen && h1 != null) {
        BrokerCalendarSheet(
            state = state,
            dates = h1.orderedDatesDescending,
            selectedDate = date,
            onSelect = { selectedDate = it; calendarOpen = false },
            onDismiss = { calendarOpen = false },
        )
    }

    selectedAlert?.let { alert ->
        h1?.let { payload ->
            EvidenceSheet(h1 = payload, alert = alert, brokerDate = date, onDismiss = { selectedAlert = null })
        }
    }
}

@Composable
private fun BrokerCalendarSheet(
    state: OAKAppState,
    dates: List<String>,
    selectedDate: String,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val p = LocalOAKPalette.current
    val initialMonth = remember(selectedDate) {
        runCatching { YearMonth.parse(selectedDate.take(7)) }.getOrElse { YearMonth.now() }
    }
    var monthAnchor by remember(selectedDate) { mutableStateOf(initialMonth) }
    val activeDates = remember(dates) { dates.toSet() }
    val firstDay = monthAnchor.atDay(1)
    val sundayOffset = firstDay.dayOfWeek.value % 7
    val monthCells = remember(monthAnchor) {
        val start = firstDay.minusDays(sundayOffset.toLong())
        List(42) { index -> start.plusDays(index.toLong()) }
    }
    val monthTitle = if (state.locale == OAKLocale.VN) {
        "Tháng ${monthAnchor.monthValue} ${monthAnchor.year}"
    } else {
        "${monthAnchor.month.getDisplayName(TextStyle.FULL, Locale.ENGLISH)} ${monthAnchor.year}"
    }
    val weekdays = if (state.locale == OAKLocale.VN) {
        listOf("CN", "T2", "T3", "T4", "T5", "T6", "T7")
    } else {
        listOf("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
    }

    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = p.canvas) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 26.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(state.text("Chọn ngày H1", "Choose H1 date"), color = p.text, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onDismiss) { Text(state.text("Đóng", "Close")) }
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { monthAnchor = monthAnchor.minusMonths(1) }) {
                    Text("‹", color = p.accent, fontSize = 30.sp, lineHeight = 30.sp, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.weight(1f))
                Text(monthTitle, color = p.text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                TextButton(onClick = { monthAnchor = monthAnchor.plusMonths(1) }) {
                    Text("›", color = p.accent, fontSize = 30.sp, lineHeight = 30.sp, fontWeight = FontWeight.Bold)
                }
            }
            Row(Modifier.fillMaxWidth()) {
                weekdays.forEach { weekday ->
                    Text(
                        weekday,
                        modifier = Modifier.weight(1f),
                        color = p.muted,
                        fontSize = if (state.locale == OAKLocale.VN) 11.sp else 9.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                }
            }
            monthCells.chunked(7).forEach { week ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    week.forEach { cellDate ->
                        val key = cellDate.toString()
                        val active = key in activeDates
                        val selected = key == selectedDate
                        val inMonth = cellDate.month == monthAnchor.month
                        val background = when {
                            selected -> p.accent
                            active -> p.accent.copy(alpha = .08f)
                            else -> Color.Transparent
                        }
                        val foreground = when {
                            selected -> Color.White
                            active -> p.text
                            inMonth -> p.muted.copy(alpha = .35f)
                            else -> p.muted.copy(alpha = .20f)
                        }
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .height(42.dp)
                                .background(background, RoundedCornerShape(10.dp))
                                .clickable(enabled = active) { onSelect(key) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(cellDate.dayOfMonth.toString(), color = foreground, fontSize = 14.sp, fontWeight = if (selected) FontWeight.Black else FontWeight.SemiBold)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun H1Matrix(h1: H1SignalPayload, date: String, onSelect: (H1SignalAlert) -> Unit) {
    val p = LocalOAKPalette.current
    val horizontal = rememberScrollState()
    OAKCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionTitle("BLOCK MATRIX", "↔ Swipe")
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Top) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    MatrixLabel("SYMBOL", 104)
                    VisibleSymbols.forEach { symbol -> MatrixLabel(symbol, 104, height = 78) }
                }
                Column(Modifier.horizontalScroll(horizontal), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        h1.hours.forEach { hour -> MatrixHour(hour) }
                    }
                    VisibleSymbols.forEach { symbol ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            h1.hours.forEach { hour ->
                                val alert = h1.alert(date, symbol, hour)
                                H1MatrixCell(
                                    alert = alert,
                                    onSelect = onSelect,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MatrixLabel(value: String, width: Int, height: Int = 52) {
    val p = LocalOAKPalette.current
    Box(
        Modifier.width(width.dp).height(height.dp).background(p.raised, RoundedCornerShape(11.dp)).padding(start = 10.dp),
        contentAlignment = Alignment.CenterStart,
    ) {
        Text(value, color = p.text, fontSize = if (height > 60) 14.sp else 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
    }
}

@Composable
private fun MatrixHour(hour: Int) {
    val p = LocalOAKPalette.current
    Column(
        modifier = Modifier.width(82.dp).height(52.dp).background(p.raised, RoundedCornerShape(11.dp)),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("H${hour.toString().padStart(2, '0')}", color = p.muted, fontSize = 13.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
    }
}

@Composable
private fun H1MatrixCell(alert: H1SignalAlert?, onSelect: (H1SignalAlert) -> Unit) {
    val p = LocalOAKPalette.current
    Column(
        modifier = Modifier
            .width(82.dp)
            .height(78.dp)
            .background(p.surface, RoundedCornerShape(11.dp))
            .then(if (alert?.entryHour != null) Modifier.clickable { onSelect(alert) } else Modifier),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        if (alert?.entryHour != null) {
            Text("H${alert.entryHour.toString().padStart(2, '0')}", color = p.text, fontSize = 16.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
            Spacer(Modifier.height(7.dp))
            when (alert.signal) {
                SignalSide.BUY -> OAKPill("BUY", PillTone.BUY)
                SignalSide.SELL -> OAKPill("SELL", PillTone.SELL)
                null -> Text("—", color = p.muted)
            }
        } else {
            Text("—", color = p.muted.copy(alpha = .55f), fontSize = 15.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
        }
    }
}

private enum class SignalFilter { ALL, BUY, SELL }

@Composable
fun SignalsScreen(state: OAKAppState) {
    val p = LocalOAKPalette.current
    val h1 = state.payload?.h1
    val date = h1?.latestDate.orEmpty()
    var filter by remember { mutableStateOf(SignalFilter.ALL) }
    var selectedAlert by remember { mutableStateOf<H1SignalAlert?>(null) }
    val rows = h1?.alerts(date, VisibleSymbols).orEmpty()
        .filter { it.entryHour != null }
        .filter {
            when (filter) {
                SignalFilter.ALL -> it.signal != null
                SignalFilter.BUY -> it.signal == SignalSide.BUY
                SignalFilter.SELL -> it.signal == SignalSide.SELL
            }
        }

    OAKScreen(state, "TRADING / SIGNALS", state.text("Tín hiệu", "Signals"), state.text("Radar BUY/SELL theo H1 và drill-down evidence M15.", "BUY/SELL H1 radar with M15 evidence drill-down.")) {
        item {
            SegmentedRow(
                choices = listOf("ALL", "BUY", "SELL"),
                selected = filter.name,
                onSelect = { filter = SignalFilter.valueOf(it) },
            )
        }
        item { SectionTitle("H1 ACTIVITY", date) }
        items(rows, key = { it.id }) { alert ->
            val tint = if (alert.signal == SignalSide.BUY) p.buy else if (alert.signal == SignalSide.SELL) p.sell else null
            OAKCard(modifier = Modifier.clickable { selectedAlert = alert }, tint = tint) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Bottom) {
                            Text(alert.symbol, color = p.text, fontSize = 18.sp, fontWeight = FontWeight.Black)
                            Text("H${alert.slotHour.toString().padStart(2, '0')}", color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            alert.entryHour?.let { OAKPill("ENTRY H$it") }
                            alert.patternGroup?.let { OAKPill(it, PillTone.ACCENT) }
                        }
                    }
                    Spacer(Modifier.weight(1f))
                    when (alert.signal) {
                        SignalSide.BUY -> OAKPill("BUY", PillTone.BUY)
                        SignalSide.SELL -> OAKPill("SELL", PillTone.SELL)
                        null -> Text("—", color = p.muted)
                    }
                }
            }
        }
        if (rows.isEmpty()) item { OAKCard { Text("No matching alerts", color = p.muted) } }
    }

    if (h1 != null) {
        selectedAlert?.let { alert -> EvidenceSheet(h1, alert, date) { selectedAlert = null } }
    }
}

@Composable
fun ReportsScreen(state: OAKAppState) {
    val p = LocalOAKPalette.current
    val reports = state.payload?.reports
    OAKScreen(state, "TRADING / REPORTS", state.text("Báo cáo", "Reports"), state.text("Tóm tắt tín hiệu H1 trên dữ liệu backend đã lưu.", "Summary of retained H1 backend signals.")) {
        if (reports != null) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard("TOTAL", reports.totalSignals.toString(), p.accent, Modifier.weight(1f))
                        MetricCard("BALANCE", "%.1f%%".format(reports.signalBalancePct), p.text, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricCard("BUY", reports.buySignals.toString(), p.buy, Modifier.weight(1f))
                        MetricCard("SELL", reports.sellSignals.toString(), p.sell, Modifier.weight(1f))
                    }
                }
            }
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionTitle(state.text("10 NGÀY GẦN NHẤT", "LAST 10 DAYS"), "SIGNAL VOLUME")
                        ReportBarChart(reports.trend)
                    }
                }
            }
            item {
                OAKCard {
                    Text(state.text("Báo cáo chỉ đọc dữ liệu H1 đã publish; không tác động tài khoản giao dịch.", "Reports read published H1 data only and never mutate trading accounts."), color = p.muted, fontSize = 14.sp, lineHeight = 21.sp)
                }
            }
        } else item { OAKCard { CircularProgressIndicator() } }
    }
}

@Composable
private fun MetricCard(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    OAKCard(modifier = modifier, tint = color) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            val p = LocalOAKPalette.current
            Text(label, color = p.muted, fontSize = 10.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace, letterSpacing = 1.2.sp)
            Text(value, color = color, fontSize = 28.sp, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun ReportBarChart(trend: List<ReportTrend>) {
    val p = LocalOAKPalette.current
    val maxValue = max(1, trend.maxOfOrNull { it.value } ?: 1)
    Column {
        Canvas(Modifier.fillMaxWidth().height(210.dp)) {
            if (trend.isEmpty()) return@Canvas
            val gap = 8.dp.toPx()
            val usable = size.width - gap * (trend.size - 1)
            val barWidth = usable / trend.size
            trend.forEachIndexed { index, point ->
                val height = (point.value.toFloat() / maxValue) * (size.height - 18.dp.toPx())
                drawRoundRect(
                    color = p.accent,
                    topLeft = Offset(index * (barWidth + gap), size.height - height),
                    size = Size(barWidth, height),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(5.dp.toPx()),
                )
            }
        }
        Row(Modifier.fillMaxWidth()) {
            trend.forEachIndexed { index, point ->
                val show = index == 0 || index == trend.lastIndex || index % 2 == 0
                Text(if (show) shortDate(point.date) else "", modifier = Modifier.weight(1f), color = p.muted, fontSize = 9.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
            }
        }
    }
}

@Composable
fun MoreScreen(state: OAKAppState) {
    val p = LocalOAKPalette.current
    val context = LocalContext.current
    val system = state.payload?.system
    val accounts = state.payload?.accounts?.accounts.orEmpty()
    OAKScreen(state, "OAK / SYSTEM", state.text("Hệ thống", "System"), state.text("Trạng thái backend, H1 feed, providers và account routing.", "Backend, H1 feed, provider and account-routing status.")) {
        item {
            OAKCard {
                Column(verticalArrangement = Arrangement.spacedBy(13.dp)) {
                    SectionTitle(state.text("GIAO DIỆN", "APPEARANCE"), "native")
                    Text("Theme", color = p.muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    SegmentedRow(listOf("Light", "Dark", "Contrast"), state.themeMode.name.lowercase().replaceFirstChar { it.uppercase() }) {
                        state.setTheme(OAKThemeMode.valueOf(it.uppercase()))
                    }
                    Text(state.text("Ngôn ngữ", "Language"), color = p.muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    SegmentedRow(listOf("VN", "EN"), state.locale.name) { state.updateLocale(OAKLocale.valueOf(it)) }
                }
            }
        }
        if (system != null) {
            item {
                OAKCard(tint = if (system.h1.ready) p.success else p.warning) {
                    Column(verticalArrangement = Arrangement.spacedBy(13.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column {
                                Text("© 2026 QuachGia", color = p.text, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                                Text("MIT License · Kotlin · Jetpack Compose · Android", color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.weight(1f))
                            OAKPill(system.apiStatus, PillTone.SUCCESS)
                        }
                        Row {
                            OAKMetric("API LATENCY", "${system.latencyMs}ms", modifier = Modifier.weight(1f), valueColor = p.accent)
                            OAKMetric("H1 FEED", if (system.h1.ready) "READY" else "WAIT", modifier = Modifier.weight(1f), valueColor = if (system.h1.ready) p.success else p.warning)
                        }
                    }
                }
            }
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(13.dp)) {
                        SectionTitle("H1 FEED", system.h1.brokerDate)
                        Row {
                            OAKMetric("SCHEMA", "v${system.h1.schemaVersion}", modifier = Modifier.weight(1f))
                            OAKMetric("RULE", "v${system.h1.signalRuleVersion}", modifier = Modifier.weight(1f))
                            OAKMetric("HISTORY", "${system.h1.historyDays} days", modifier = Modifier.weight(1f), valueColor = p.accent)
                            OAKMetric("SYMBOLS/BLOCKS", "${system.h1.symbolCount} / ${system.h1.blockCount}", modifier = Modifier.weight(1f))
                        }
                        HorizontalDivider(color = p.border.copy(alpha = .55f))
                        Text(system.h1.profile.ifBlank { "—" }, color = p.text, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                    }
                }
            }
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionTitle("PROVIDERS", "${system.accounts.enabled}/${system.accounts.total} enabled")
                        ProviderRow("cTrader", "Scope: ${system.providers.ctraderScope}", system.providers.ctraderConnected)
                        HorizontalDivider(color = p.border.copy(alpha = .55f))
                        ProviderRow("MT5", "${system.providers.mt5OnlineAccounts}/${system.providers.mt5TotalAccounts} local heartbeat online", system.providers.mt5Connected)
                    }
                }
            }
        }
        if (accounts.isNotEmpty()) {
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionTitle("ACCOUNTS", "${accounts.size} total")
                        accounts.forEachIndexed { index, account ->
                            AccountRow(state, account)
                            if (index != accounts.lastIndex) HorizontalDivider(color = p.border.copy(alpha = .55f))
                        }
                    }
                }
            }
        }
        item {
            OAKCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, "https://www.oakgatekeeper.uk".toUri())) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = p.raised, contentColor = p.accent),
                    ) { Text(state.text("MỞ WEB", "OPEN WEB"), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black) }
                    Button(
                        onClick = { state.signOut() },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = p.raised, contentColor = p.danger),
                    ) { Text(state.text("ĐĂNG XUẤT", "SIGN OUT"), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black) }
                }
            }
        }
    }
}

@Composable
private fun ProviderRow(name: String, detail: String, online: Boolean) {
    val p = LocalOAKPalette.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(9.dp).background(if (online) p.success else p.warning, RoundedCornerShape(999.dp)))
        Spacer(Modifier.width(11.dp))
        Column {
            Text(name, color = p.text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text(detail, color = p.muted, fontSize = 13.sp)
        }
        Spacer(Modifier.weight(1f))
        OAKPill(if (online) "ONLINE" else "OFFLINE", if (online) PillTone.SUCCESS else PillTone.WARNING)
    }
}

@Composable
private fun AccountRow(state: OAKAppState, account: ProviderAccount) {
    val p = LocalOAKPalette.current
    val local = account.bridgeRuntime?.startsWith("local-primary") == true
    val status = if (account.provider == "mt5") {
        when {
            account.bridgeOnline == true -> if (local) "Local heartbeat online" else "EA heartbeat online"
            account.bridgeRuntime == "local-primary-offline" -> "Local heartbeat offline"
            local -> "Local heartbeat pending"
            else -> "Heartbeat unavailable"
        }
    } else null
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(7.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(account.label, color = p.text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                if (account.isDefault) OAKPill("DEFAULT", PillTone.ACCENT)
            }
            Text("${account.provider.uppercase()} · ${account.broker} · ${account.traderLogin ?: account.externalAccountId}", color = p.muted, fontSize = 13.sp)
            status?.let { Text(it, color = if (account.bridgeOnline == true) p.success else p.warning, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        }
        Switch(checked = account.enabled, onCheckedChange = { state.toggleAccount(account.id, it) })
    }
}

@Composable
private fun SegmentedRow(choices: List<String>, selected: String, onSelect: (String) -> Unit) {
    val p = LocalOAKPalette.current
    Row(
        modifier = Modifier.fillMaxWidth().background(p.raised, RoundedCornerShape(999.dp)).padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        choices.forEach { choice ->
            val active = choice.equals(selected, ignoreCase = true)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .background(if (active) p.surface else Color.Transparent, RoundedCornerShape(999.dp))
                    .clickable { onSelect(choice) }
                    .padding(vertical = 10.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(choice, color = if (active) p.text else p.muted, fontSize = 14.sp, fontWeight = if (active) FontWeight.Bold else FontWeight.Medium)
            }
        }
    }
}

@Composable
private fun EvidenceSheet(h1: H1SignalPayload, alert: H1SignalAlert, brokerDate: String, onDismiss: () -> Unit) {
    val p = LocalOAKPalette.current
    val context = LocalContext.current
    val facts = h1.evidenceFacts(brokerDate, alert)
    var copiedChart by remember(alert.id, brokerDate) { mutableStateOf(false) }
    LaunchedEffect(copiedChart) {
        if (copiedChart) {
            delay(1_400)
            copiedChart = false
        }
    }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = p.canvas) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column {
                        OAKEyebrow("H1 / EVIDENCE")
                        Text("${alert.symbol} · H${alert.slotHour.toString().padStart(2, '0')}", color = p.text, fontSize = 28.sp, fontWeight = FontWeight.Black)
                    }
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = onDismiss) { Text("Đóng") }
                }
            }
            item { CandlestickChart(alert.sampleBars) }
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        SectionTitle("KEY FACTS")
                        Fact("BROKER DAY", brokerDate)
                        Fact("BLOCK", "H${alert.slotHour}")
                        Fact("ENTRY", alert.entryHour?.let { "H$it" } ?: "—")
                        Fact("GROUP", alert.patternGroup ?: "—")
                        Fact("FAMILY", evidenceFamilyLabel(alert.patternFamily))
                        Fact("PATTERN", evidencePatternLabel(alert.pattern))
                        Fact("PATTERN SRC", facts.patternSource)
                        Fact("BASE CANDLE", facts.rawBase)
                        if (facts.signalSource.isNotBlank()) Fact("FINAL SOURCE", facts.signalSource)
                        Fact("RULE", facts.rule)
                        Fact("FINAL", facts.finalSignal)
                    }
                }
            }
            item {
                OAKCard {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        SectionTitle("PATTERN BARS", "NEWEST → OLDEST")
                        alert.sampleBars.forEachIndexed { index, bar ->
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text("#${index + 1}", modifier = Modifier.width(42.dp), color = p.muted, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
                                Column(Modifier.weight(1f)) {
                                    Text("${bar.brokerDate} · ${bar.brokerTime}", color = p.text, fontSize = 15.sp, fontWeight = FontWeight.Black)
                                    Text("O ${bar.open} · H ${bar.high} · L ${bar.low} · C ${bar.close}", color = p.muted, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                                }
                                OAKPill(bar.direction, if (bar.direction == "T") PillTone.BUY else PillTone.SELL)
                            }
                            if (index != alert.sampleBars.lastIndex) HorizontalDivider(color = p.border.copy(alpha = .45f))
                        }
                    }
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = {
                            val copied = ShareStore.copyChartToClipboard(context, alert, brokerDate)
                            copiedChart = copied
                            Toast.makeText(
                                context,
                                if (copied) "Chart PNG copied · ready to paste in Telegram" else "Unable to copy chart PNG",
                                Toast.LENGTH_SHORT,
                            ).show()
                        },
                        modifier = Modifier.weight(1f),
                    ) { Text(if (copiedChart) "✓ COPIED" else "COPY CHART", fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace) }
                    Button(
                        onClick = {
                            if (!ShareStore.shareChart(context, alert, brokerDate)) {
                                Toast.makeText(context, "Unable to open chart sharing", Toast.LENGTH_SHORT).show()
                            }
                        },
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = p.raised, contentColor = p.accent),
                    ) { Text("SHARE CHART", fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace) }
                }
            }
        }
    }
}

private fun evidenceFamilyLabel(value: String?): String = when (value) {
    "ALT" -> "GT/TG"
    "SAME" -> "TT/GG"
    else -> value ?: "—"
}

private fun evidencePatternLabel(value: String?): String =
    value?.takeIf { it.isNotBlank() }?.toCharArray()?.joinToString(" ") ?: "—"

@Composable
private fun Fact(label: String, value: String) {
    val p = LocalOAKPalette.current
    Row(Modifier.fillMaxWidth()) {
        Text(label, modifier = Modifier.width(94.dp), color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
        Text(value, color = p.text, fontSize = 15.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
    }
}

@Composable
private fun CandlestickChart(bars: List<H1SampleBar>) {
    val p = LocalOAKPalette.current
    val safe = bars.sortedWith(
        compareBy<H1SampleBar> { it.brokerDate }
            .thenBy { it.hour }
            .thenBy { it.minute },
    ).take(6)
    OAKCard {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SectionTitle("M15 CHART", "OLDEST → NEWEST")
            if (safe.isEmpty()) {
                Text("No M15 bars", color = p.muted)
                return@Column
            }
            val maxPrice = safe.maxOf { it.high }
            val minPrice = safe.minOf { it.low }
            val range = (maxPrice - minPrice).takeIf { it > 0 } ?: 1.0
            Canvas(Modifier.fillMaxWidth().height(160.dp)) {
                val slot = size.width / safe.size
                safe.forEachIndexed { index, bar ->
                    val centerX = slot * index + slot / 2
                    fun y(price: Double): Float = ((maxPrice - price) / range * (size.height - 18.dp.toPx()) + 8.dp.toPx()).toFloat()
                    val up = bar.close >= bar.open
                    val color = if (up) p.buy else p.sell
                    drawLine(color, Offset(centerX, y(bar.high)), Offset(centerX, y(bar.low)), strokeWidth = 3.dp.toPx(), cap = StrokeCap.Round)
                    val top = minOf(y(bar.open), y(bar.close))
                    val bottom = maxOf(y(bar.open), y(bar.close))
                    val bodyHeight = max(3.dp.toPx(), bottom - top)
                    drawRoundRect(color, Offset(centerX - slot * .18f, top), Size(slot * .36f, bodyHeight), androidx.compose.ui.geometry.CornerRadius(4.dp.toPx()))
                }
            }
            Row(Modifier.fillMaxWidth()) {
                safe.forEach { bar ->
                    Text(
                        bar.brokerTime,
                        modifier = Modifier.weight(1f),
                        color = p.muted,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        maxLines = 1,
                    )
                }
            }
        }
    }
}

@Composable
private fun OAKScreen(
    state: OAKAppState,
    eyebrow: String,
    title: String,
    subtitle: String,
    content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit,
) {
    val p = LocalOAKPalette.current
    LazyColumn(
        modifier = Modifier.fillMaxSize().background(p.canvas),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { OAKPageHeader(eyebrow, title, subtitle) }
        if (state.errorMessage.isNotBlank()) item { Text(state.errorMessage, color = p.danger, fontSize = 13.sp, fontWeight = FontWeight.Bold) }
        content()
        item {
            TextButton(onClick = { state.refreshAsync() }, modifier = Modifier.fillMaxWidth()) {
                Text(if (state.isRefreshing) state.text("ĐANG LÀM MỚI…", "REFRESHING…") else state.text("LÀM MỚI", "REFRESH"), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

private fun shortPublished(value: String): String = value.takeIf { it.length >= 16 }?.let { "${it.substring(11, 16)} ${it.substring(8, 10)}-${it.substring(5, 7)}" } ?: value
private fun displayDate(value: String): String = value.split('-').takeIf { it.size == 3 }?.let { "${it[2]} / ${it[1]} / ${it[0]}" } ?: value
private fun shortDate(value: String): String = value.split('-').takeIf { it.size == 3 }?.let { "${it[2]}/${it[1]}" } ?: value
