package uk.oakgatekeeper.mobile

import android.content.ComponentCallbacks2
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.annotation.DrawableRes
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val state: OAKAppState = viewModel()
            OAKTheme(state.themeMode) { OAKRoot(state) }
        }
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        if (level >= ComponentCallbacks2.TRIM_MEMORY_UI_HIDDEN) ShareStore.trimTransient(this)
    }

    override fun onLowMemory() {
        super.onLowMemory()
        ShareStore.trimTransient(this)
    }
}

@Composable
private fun OAKLaunchLoading(state: OAKAppState) {
    val p = LocalOAKPalette.current
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Image(
                painter = painterResource(R.drawable.oak_app_icon_exact),
                contentDescription = "OAK Gatekeeper",
                modifier = Modifier.size(104.dp),
            )
            Text("OAK GATEKEEPER", color = p.text, fontSize = 15.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
            CircularProgressIndicator(color = p.accent, strokeWidth = 2.dp, modifier = Modifier.size(24.dp))
            Text(state.text("Đang đồng bộ H1 local…", "Syncing local H1…"), color = p.muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

private data class TabSpec(val tab: OAKTab, val vn: String, val en: String, @DrawableRes val iconRes: Int)

private val tabs = listOf(
    TabSpec(OAKTab.LIVE, "Live", "Live", R.drawable.ic_tab_live),
    TabSpec(OAKTab.HISTORY, "Lịch sử", "History", R.drawable.ic_tab_history),
    TabSpec(OAKTab.SIGNALS, "Tín hiệu", "Signals", R.drawable.ic_tab_signals),
    TabSpec(OAKTab.REPORTS, "Báo cáo", "Reports", R.drawable.ic_tab_reports),
    TabSpec(OAKTab.MORE, "Thêm", "More", R.drawable.ic_tab_more),
)

@Composable
private fun OAKRoot(state: OAKAppState) {
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(state.isUnlocked, lifecycleOwner) {
        if (!state.isUnlocked) return@LaunchedEffect
        lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (isActive && state.isUnlocked) {
                state.refresh(forceLoading = state.payload == null)
                delay(20_000)
            }
        }
    }

    if (!state.isUnlocked) {
        UnlockScreen(state)
        return
    }

    if (state.payload == null && state.errorMessage.isBlank()) {
        OAKLaunchLoading(state)
        return
    }

    val p = LocalOAKPalette.current
    Scaffold(
        containerColor = p.canvas,
        bottomBar = {
            Surface(
                modifier = Modifier
                    .padding(horizontal = 16.dp, vertical = 8.dp)
                    .windowInsetsPadding(WindowInsets.navigationBars),
                shape = RoundedCornerShape(32.dp),
                color = p.surface.copy(alpha = .98f),
                shadowElevation = 8.dp,
                tonalElevation = 0.dp,
                border = androidx.compose.foundation.BorderStroke(1.dp, p.border.copy(alpha = .55f)),
            ) {
                NavigationBar(containerColor = androidx.compose.ui.graphics.Color.Transparent, tonalElevation = 0.dp) {
                    tabs.forEach { item ->
                        val selected = state.selectedTab == item.tab
                        NavigationBarItem(
                            selected = selected,
                            onClick = { state.selectedTab = item.tab },
                            icon = { Icon(painterResource(item.iconRes), contentDescription = state.text(item.vn, item.en)) },
                            label = { Text(state.text(item.vn, item.en)) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = p.accent,
                                selectedTextColor = p.accent,
                                indicatorColor = p.raised,
                                unselectedIconColor = p.text,
                                unselectedTextColor = p.text,
                            ),
                        )
                    }
                }
            }
        },
    ) { inner ->
        Box(Modifier.fillMaxSize().padding(inner)) {
            when (state.selectedTab) {
                OAKTab.LIVE -> H1BoardScreen(state, history = false)
                OAKTab.HISTORY -> H1BoardScreen(state, history = true)
                OAKTab.SIGNALS -> SignalsScreen(state)
                OAKTab.REPORTS -> ReportsScreen(state)
                OAKTab.MORE -> MoreScreen(state)
            }
        }
    }
}
