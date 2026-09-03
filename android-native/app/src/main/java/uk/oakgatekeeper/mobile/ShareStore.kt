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

    fun trimTransient(context: Context) {
        File(context.cacheDir, "shared-charts").listFiles()?.forEach { it.delete() }
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
