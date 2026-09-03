package uk.oakgatekeeper.mobile

import android.app.Application
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

enum class OAKTab { LIVE, HISTORY, SIGNALS, REPORTS, MORE }
enum class OAKThemeMode { LIGHT, DARK, CONTRAST }
enum class OAKLocale { VN, EN }

class OAKAppState(application: Application) : AndroidViewModel(application) {
    private val prefs = application.getSharedPreferences("oak.native", Context.MODE_PRIVATE)
    private val secureStore = SecureStore(application)
    private val api = OAKApiClient()

    var selectedTab by mutableStateOf(OAKTab.LIVE)
    var apiKey by mutableStateOf(secureStore.read())
        private set
    var payload by mutableStateOf<MobileAppPayload?>(null)
        private set
    var isLoading by mutableStateOf(false)
        private set
    var isRefreshing by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf("")
        private set
    var themeMode by mutableStateOf(runCatching { OAKThemeMode.valueOf(prefs.getString("theme", "LIGHT")!!) }.getOrDefault(OAKThemeMode.LIGHT))
        private set
    var locale by mutableStateOf(runCatching { OAKLocale.valueOf(prefs.getString("locale", "VN")!!) }.getOrDefault(OAKLocale.VN))
        private set

    val isUnlocked: Boolean get() = apiKey.isNotBlank()

    fun text(vn: String, en: String): String = if (locale == OAKLocale.VN) vn else en

    fun setTheme(next: OAKThemeMode) {
        themeMode = next
        prefs.edit().putString("theme", next.name).apply()
    }

    fun updateLocale(next: OAKLocale) {
        locale = next
        prefs.edit().putString("locale", next.name).apply()
    }

    suspend fun unlock(candidate: String) {
        val key = candidate.trim()
        require(key.isNotEmpty()) { "Dashboard API key is required" }
        api.fetchAccounts(key)
        secureStore.write(key)
        apiKey = key
        errorMessage = ""
        refresh(forceLoading = true)
    }

    fun signOut() {
        secureStore.clear()
        apiKey = ""
        payload = null
        selectedTab = OAKTab.LIVE
    }

    suspend fun refresh(forceLoading: Boolean = false) {
        if (!isUnlocked || isRefreshing) return
        if (forceLoading || payload == null) isLoading = true
        isRefreshing = true
        try {
            payload = api.fetchApp(apiKey)
            errorMessage = ""
        } catch (error: Throwable) {
            errorMessage = error.message ?: error.javaClass.simpleName
        } finally {
            isLoading = false
            isRefreshing = false
        }
    }

    fun refreshAsync() {
        viewModelScope.launch { refresh() }
    }

    fun toggleAccount(id: String, enabled: Boolean) {
        if (!isUnlocked) return
        val previous = payload
        applyAccountEnabledLocally(id, enabled)
        viewModelScope.launch {
            try {
                val accounts = api.setAccountEnabled(apiKey, id, enabled)
                applyAccountSnapshot(accounts)
                errorMessage = ""
                refresh()
            } catch (error: Throwable) {
                payload = previous
                errorMessage = error.message ?: error.javaClass.simpleName
            }
        }
    }

    private fun applyAccountEnabledLocally(id: String, enabled: Boolean) {
        val current = payload ?: return
        val next = current.accounts.copy(
            accounts = current.accounts.accounts.map { if (it.id == id) it.withEnabled(enabled) else it }
        )
        applyAccountSnapshot(next)
    }

    private fun applyAccountSnapshot(accounts: AccountsPayload) {
        val current = payload ?: return
        val system = current.system.copy(
            accounts = current.system.accounts.copy(
                total = accounts.accounts.size,
                enabled = accounts.accounts.count { it.enabled },
                defaultAccountId = accounts.defaultAccountId,
            )
        )
        payload = current.copy(accounts = accounts, system = system)
    }
}

class OAKApiClient(private val baseUrl: String = "https://www.oakgatekeeper.uk") {
    suspend fun fetchApp(apiKey: String): MobileAppPayload = withContext(Dispatchers.IO) {
        OAKJson.app(request("/api/mobile/app", apiKey))
    }

    suspend fun fetchAccounts(apiKey: String): AccountsPayload = withContext(Dispatchers.IO) {
        OAKJson.accountsEnvelope(request("/api/accounts", apiKey))
    }

    suspend fun setAccountEnabled(apiKey: String, id: String, enabled: Boolean): AccountsPayload = withContext(Dispatchers.IO) {
        val body = JSONObject().put("id", id).put("enabled", enabled).toString()
        OAKJson.accountsEnvelope(request("/api/accounts", apiKey, "PATCH", body))
    }

    private fun request(path: String, apiKey: String, method: String = "GET", body: String? = null): String {
        val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 12_000
            connection.readTimeout = 20_000
            connection.useCaches = false
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("x-api-key", apiKey)
            if (body != null) {
                connection.doOutput = true
                connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (code == 401 || code == 403) error("Dashboard API key is invalid or expired")
            if (code !in 200..299) {
                val message = runCatching { JSONObject(text).optString("error") }.getOrNull().orEmpty()
                error("OAK API $code: ${message.ifBlank { connection.responseMessage }}")
            }
            return text
        } finally {
            connection.disconnect()
        }
    }
}

private class SecureStore(context: Context) {
    private val prefs = context.getSharedPreferences("oak.secure", Context.MODE_PRIVATE)
    private val alias = "oak.dashboard.api-key.v1"

    fun read(): String {
        val iv = prefs.getString("iv", null) ?: return ""
        val cipherText = prefs.getString("cipher", null) ?: return ""
        return runCatching {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
            String(cipher.doFinal(Base64.decode(cipherText, Base64.NO_WRAP)), Charsets.UTF_8)
        }.getOrDefault("")
    }

    fun write(value: String) {
        if (value.isBlank()) {
            clear()
            return
        }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("cipher", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setUserAuthenticationRequired(false)
                .build()
        )
        return generator.generateKey()
    }
}
