package uk.oakgatekeeper.mobile

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class OAKPalette(
    val canvas: Color,
    val surface: Color,
    val raised: Color,
    val border: Color,
    val borderStrong: Color,
    val text: Color,
    val muted: Color,
    val accent: Color,
    val accentStrong: Color,
    val buy: Color,
    val sell: Color,
    val warning: Color,
    val success: Color,
    val danger: Color,
)

private val LightPalette = OAKPalette(
    canvas = Color(0xFFF2F6FA), surface = Color(0xFFF8FAFD), raised = Color(0xFFEEF3F8),
    border = Color(0xFF9CAABD), borderStrong = Color(0xFF68788E), text = Color(0xFF0A101A),
    muted = Color(0xFF4F5C70), accent = Color(0xFF2E6DCC), accentStrong = Color(0xFF174EA6),
    buy = Color(0xFF238557), sell = Color(0xFFC63A32), warning = Color(0xFF9B5B00),
    success = Color(0xFF198754), danger = Color(0xFFB42318),
)

private val DarkPalette = OAKPalette(
    canvas = Color(0xFF07111A), surface = Color(0xFF0E1926), raised = Color(0xFF142232),
    border = Color(0xFF26384A), borderStrong = Color(0xFF3A5067), text = Color(0xFFF4F7FB),
    muted = Color(0xFF8FA2B8), accent = Color(0xFF2E6DCC), accentStrong = Color(0xFF174EA6),
    buy = Color(0xFF238557), sell = Color(0xFFC63A32), warning = Color(0xFF9B5B00),
    success = Color(0xFF198754), danger = Color(0xFFB42318),
)

private val ContrastPalette = OAKPalette(
    canvas = Color.Black, surface = Color(0xFF050505), raised = Color(0xFF111111),
    border = Color(0xFF738199), borderStrong = Color.White, text = Color.White,
    muted = Color(0xFFD1D9E6), accent = Color(0xFF66A3FF), accentStrong = Color(0xFF9BC2FF),
    buy = Color(0xFF45E38B), sell = Color(0xFFFF716B), warning = Color(0xFFFFD166),
    success = Color(0xFF4ADE80), danger = Color(0xFFFF5B5B),
)

val LocalOAKPalette = staticCompositionLocalOf { LightPalette }

@Composable
fun OAKTheme(mode: OAKThemeMode, content: @Composable () -> Unit) {
    val palette = when (mode) {
        OAKThemeMode.LIGHT -> LightPalette
        OAKThemeMode.DARK -> DarkPalette
        OAKThemeMode.CONTRAST -> ContrastPalette
    }
    val scheme = if (mode == OAKThemeMode.LIGHT) {
        lightColorScheme(
            primary = palette.accent,
            background = palette.canvas,
            surface = palette.surface,
            onPrimary = Color.White,
            onBackground = palette.text,
            onSurface = palette.text,
        )
    } else {
        darkColorScheme(
            primary = palette.accent,
            background = palette.canvas,
            surface = palette.surface,
            onPrimary = Color.White,
            onBackground = palette.text,
            onSurface = palette.text,
        )
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalOAKPalette provides palette) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

@Composable
fun OAKPageHeader(eyebrow: String, title: String, subtitle: String) {
    val p = LocalOAKPalette.current
    Column(verticalArrangement = Arrangement.spacedBy(7.dp), modifier = Modifier.fillMaxWidth()) {
        OAKEyebrow(eyebrow)
        Text(title, color = p.text, fontSize = 34.sp, lineHeight = 38.sp, fontWeight = FontWeight.Black)
        Text(subtitle, color = p.muted, fontSize = 15.sp, lineHeight = 22.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun OAKEyebrow(text: String) {
    val p = LocalOAKPalette.current
    Text(
        text.uppercase(),
        color = p.accent,
        fontSize = 11.sp,
        fontWeight = FontWeight.Black,
        fontFamily = FontFamily.Monospace,
        letterSpacing = 2.sp,
    )
}

@Composable
fun OAKCard(
    modifier: Modifier = Modifier,
    tint: Color? = null,
    content: @Composable () -> Unit,
) {
    val p = LocalOAKPalette.current
    val shape = RoundedCornerShape(18.dp)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(p.surface, shape)
            .border(if (tint == null) 1.dp else 1.4.dp, (tint ?: p.border).copy(alpha = if (tint == null) .7f else .5f), shape)
            .padding(14.dp)
    ) { content() }
}

enum class PillTone { MUTED, ACCENT, BUY, SELL, WARNING, SUCCESS }

@Composable
fun OAKPill(label: String, tone: PillTone = PillTone.MUTED) {
    val p = LocalOAKPalette.current
    val color = when (tone) {
        PillTone.MUTED -> p.muted
        PillTone.ACCENT -> p.accent
        PillTone.BUY -> p.buy
        PillTone.SELL -> p.sell
        PillTone.WARNING -> p.warning
        PillTone.SUCCESS -> p.success
    }
    Text(
        label,
        modifier = Modifier
            .background(color.copy(alpha = .10f), RoundedCornerShape(999.dp))
            .border(1.6.dp, color.copy(alpha = .9f), RoundedCornerShape(999.dp))
            .padding(horizontal = 9.dp, vertical = 5.dp),
        color = color,
        fontSize = 11.sp,
        lineHeight = 13.sp,
        fontWeight = FontWeight.Black,
        fontFamily = FontFamily.Monospace,
        letterSpacing = .7.sp,
    )
}

@Composable
fun OAKMetric(label: String, value: String, modifier: Modifier = Modifier, valueColor: Color? = null) {
    val p = LocalOAKPalette.current
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(
            label.uppercase(),
            color = p.muted,
            fontSize = 10.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 1.2.sp,
        )
        Text(
            value,
            color = valueColor ?: p.text,
            fontSize = 18.sp,
            lineHeight = 22.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
        )
    }
}

@Composable
fun SectionTitle(title: String, meta: String = "") {
    val p = LocalOAKPalette.current
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title.uppercase(), color = p.text, fontSize = 13.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace, letterSpacing = 1.sp)
        Spacer(Modifier.weight(1f))
        if (meta.isNotBlank()) Text(meta, color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun MetricDivider() {
    val p = LocalOAKPalette.current
    Spacer(Modifier.width(9.dp))
    Box(Modifier.width(1.dp).height(42.dp).background(p.border.copy(alpha = .55f)))
    Spacer(Modifier.width(9.dp))
}
