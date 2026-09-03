package uk.oakgatekeeper.mobile

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import androidx.core.content.FileProvider
import androidx.core.graphics.createBitmap
import java.io.File
import java.io.FileOutputStream
import kotlin.math.max
import kotlin.math.min

object ShareStore {
    private const val Authority = "uk.oakgatekeeper.mobile.files"
    private const val Width = 900
    private const val Height = 360

    fun copyChartToClipboard(context: Context, alert: H1SignalAlert, brokerDate: String): Boolean = runCatching {
        val bitmap = renderChart(alert, brokerDate)
        val directory = File(context.cacheDir, "shared-charts").apply { mkdirs() }
        directory.listFiles()?.forEach { if (it.name != "keep") it.delete() }
        val file = File(directory, "oak-${alert.symbol}-h${alert.slotHour}-$brokerDate.png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        val uri = FileProvider.getUriForFile(context, Authority, file)
        val clipboard = context.getSystemService(ClipboardManager::class.java)
        clipboard.setPrimaryClip(ClipData.newUri(context.contentResolver, "OAK H1 chart", uri))
        true
    }.getOrDefault(false)

    fun copyScheduleToClipboard(context: Context, h1: H1SignalPayload, brokerDate: String, symbols: List<String>): Boolean = runCatching {
        val bitmap = renderSchedule(h1, brokerDate, symbols)
        val directory = File(context.cacheDir, "shared-charts").apply { mkdirs() }
        directory.listFiles()?.forEach { if (it.name.startsWith("oak-h1-scanner-")) it.delete() }
        val file = File(directory, "oak-h1-scanner-$brokerDate.png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        val uri = FileProvider.getUriForFile(context, Authority, file)
        val clipboard = context.getSystemService(ClipboardManager::class.java)
        clipboard.setPrimaryClip(ClipData.newUri(context.contentResolver, "OAK H1 schedule", uri))
        true
    }.getOrDefault(false)

    fun trimTransient(context: Context) {
        File(context.cacheDir, "shared-charts").listFiles()?.forEach { it.delete() }
    }

    private fun renderSchedule(h1: H1SignalPayload, brokerDate: String, symbols: List<String>): Bitmap {
        val hours = h1.hours
        val width = 980
        val headerHeight = 110
        val rowHeight = 92
        val symbolWidth = 150
        val cellWidth = ((width - 40 - symbolWidth) / max(1, hours.size)).coerceAtLeast(95)
        val height = headerHeight + 54 + symbols.size * rowHeight + 36
        val bitmap = createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        canvas.drawColor(Color.rgb(248, 250, 253))
        paint.typeface = android.graphics.Typeface.create(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD)
        paint.color = Color.rgb(10, 16, 26)
        paint.textSize = 28f
        canvas.drawText("OAK GATEKEEPER · H1 SCANNER", 28f, 38f, paint)
        paint.textSize = 19f
        paint.color = Color.rgb(79, 92, 112)
        canvas.drawText("Broker day: $brokerDate · MT5 ICMarkets Local · rule v${h1.signalRuleVersion ?: 0}", 28f, 72f, paint)

        val left = 20f
        val top = headerHeight.toFloat()
        fun cellRect(x: Float, y: Float, w: Float, h: Float, fill: Int, stroke: Int) {
            paint.style = Paint.Style.FILL
            paint.color = fill
            canvas.drawRoundRect(x, y, x + w, y + h, 12f, 12f, paint)
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = 2f
            paint.color = stroke
            canvas.drawRoundRect(x, y, x + w, y + h, 12f, 12f, paint)
            paint.style = Paint.Style.FILL
        }
        cellRect(left, top, symbolWidth - 6f, 46f, Color.rgb(238, 243, 248), Color.rgb(212, 220, 230))
        paint.color = Color.rgb(10, 16, 26); paint.textSize = 15f
        canvas.drawText("SYMBOL", left + 14f, top + 29f, paint)
        hours.forEachIndexed { index, hour ->
            val x = left + symbolWidth + index * cellWidth
            cellRect(x, top, cellWidth - 6f, 46f, Color.rgb(238, 243, 248), Color.rgb(212, 220, 230))
            paint.color = Color.rgb(79, 92, 112); paint.textSize = 15f; paint.textAlign = Paint.Align.CENTER
            canvas.drawText("H${hour.toString().padStart(2, '0')}", x + (cellWidth - 6f) / 2f, top + 29f, paint)
            paint.textAlign = Paint.Align.LEFT
        }
        val manualClose = h1.manualCloseH16(brokerDate)
        symbols.forEachIndexed { rowIndex, symbol ->
            val y = top + 54f + rowIndex * rowHeight
            cellRect(left, y, symbolWidth - 6f, rowHeight - 6f, Color.rgb(238, 243, 248), Color.rgb(212, 220, 230))
            paint.color = Color.rgb(10, 16, 26); paint.textSize = 17f
            canvas.drawText(symbol, left + 14f, y + 48f, paint)
            hours.forEachIndexed { colIndex, hour ->
                val x = left + symbolWidth + colIndex * cellWidth
                val alert = h1.alert(brokerDate, symbol, hour)
                val close = manualClose && hour == 16
                val reference = (symbol == "XAUUSD" && hour in listOf(3, 6)) || (symbol == "GBPUSD" && hour in listOf(9, 12, 14, 16))
                val fill = when {
                    close -> Color.rgb(255, 244, 224)
                    reference -> Color.rgb(232, 241, 255)
                    else -> Color.rgb(248, 250, 253)
                }
                val stroke = when {
                    close -> Color.rgb(155, 91, 0)
                    reference -> Color.rgb(46, 109, 204)
                    else -> Color.rgb(212, 220, 230)
                }
                cellRect(x, y, cellWidth - 6f, rowHeight - 6f, fill, stroke)
                paint.textAlign = Paint.Align.CENTER
                paint.color = Color.rgb(10, 16, 26); paint.textSize = 17f
                val entry = alert?.entryHour?.let { "H${it.toString().padStart(2, '0')}" } ?: "—"
                canvas.drawText(entry, x + (cellWidth - 6f) / 2f, y + 33f, paint)
                val signal = when {
                    close -> "CLOSE"
                    alert?.signal == SignalSide.BUY -> "BUY"
                    alert?.signal == SignalSide.SELL -> "SELL"
                    else -> ""
                }
                if (signal.isNotEmpty()) {
                    paint.color = when (signal) {
                        "BUY" -> Color.rgb(35, 133, 87)
                        "SELL" -> Color.rgb(198, 58, 50)
                        else -> Color.rgb(155, 91, 0)
                    }
                    paint.textSize = 14f
                    canvas.drawText(signal, x + (cellWidth - 6f) / 2f, y + 61f, paint)
                }
                paint.textAlign = Paint.Align.LEFT
            }
        }
        return bitmap
    }

    private fun renderChart(alert: H1SignalAlert, brokerDate: String): Bitmap {
        val bitmap = createBitmap(Width, Height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        canvas.drawColor(Color.rgb(248, 250, 253))

        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 2f
        paint.color = Color.rgb(156, 170, 189)
        canvas.drawRoundRect(18f, 18f, 882f, 342f, 20f, 20f, paint)

        paint.style = Paint.Style.FILL
        paint.color = Color.rgb(10, 16, 26)
        paint.typeface = android.graphics.Typeface.create(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD)
        paint.textSize = 23f
        canvas.drawText("OAK H1 · ${alert.symbol} H${alert.slotHour.toString().padStart(2, '0')} · $brokerDate", 42f, 46f, paint)
        paint.color = Color.rgb(79, 92, 112)
        paint.textSize = 15f
        canvas.drawText("${alert.patternGroup ?: "—"} · ${alert.patternFamily ?: "—"} · ${alert.pattern ?: "—"}", 42f, 70f, paint)

        val bars = alert.sampleBars.take(6)
        if (bars.isEmpty()) return bitmap
        val maxPrice = bars.maxOf { it.high }
        val minPrice = bars.minOf { it.low }
        val range = (maxPrice - minPrice).takeIf { it > 0 } ?: 1.0
        val left = 42f
        val right = 876f
        val top = 82f
        val bottom = 308f
        val slot = (right - left) / bars.size
        fun y(price: Double): Float = (top + ((maxPrice - price) / range) * (bottom - top)).toFloat()

        paint.color = Color.rgb(212, 220, 230)
        paint.strokeWidth = 1.5f
        canvas.drawLine(left, bottom, right, bottom, paint)

        bars.forEachIndexed { index, bar ->
            val center = left + slot * index + slot / 2f
            val up = bar.close >= bar.open
            val color = if (up) Color.rgb(35, 133, 87) else Color.rgb(198, 58, 50)
            paint.color = color
            paint.strokeWidth = 4f
            paint.strokeCap = Paint.Cap.ROUND
            canvas.drawLine(center, y(bar.high), center, y(bar.low), paint)
            val bodyTop = min(y(bar.open), y(bar.close))
            val bodyBottom = max(y(bar.open), y(bar.close))
            paint.style = Paint.Style.FILL
            canvas.drawRoundRect(center - 27f, bodyTop, center + 27f, max(bodyTop + 4f, bodyBottom), 5f, 5f, paint)

            paint.color = Color.rgb(79, 92, 112)
            paint.textSize = 18f
            paint.textAlign = Paint.Align.CENTER
            paint.typeface = android.graphics.Typeface.create(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD)
            canvas.drawText(bar.brokerTime, center, 338f, paint)
            paint.textAlign = Paint.Align.LEFT
        }
        return bitmap
    }
}
