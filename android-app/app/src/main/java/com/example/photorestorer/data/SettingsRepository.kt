package com.example.photorestorer.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

/** User-facing settings persisted via DataStore. */
data class AppSettings(
    val wifiOnly: Boolean = false,
    val defaultMode: RestorationMode = RestorationMode.NATURAL,
    val defaultOutput: OutputSize = OutputSize.X4,
    val deleteCloudAfterDownload: Boolean = true,
    val removeLocationMetadata: Boolean = true,
)

@Singleton
class SettingsRepository @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private object Keys {
        val WIFI_ONLY = booleanPreferencesKey("wifi_only")
        val DEFAULT_MODE = stringPreferencesKey("default_mode")
        val DEFAULT_OUTPUT = stringPreferencesKey("default_output")
        val DELETE_AFTER_DOWNLOAD = booleanPreferencesKey("delete_after_download")
        val REMOVE_LOCATION = booleanPreferencesKey("remove_location")
    }

    val settings: Flow<AppSettings> = context.dataStore.data.map { prefs ->
        AppSettings(
            wifiOnly = prefs[Keys.WIFI_ONLY] ?: false,
            defaultMode = RestorationMode.fromWire(prefs[Keys.DEFAULT_MODE] ?: "natural"),
            defaultOutput = OutputSize.fromWire(prefs[Keys.DEFAULT_OUTPUT] ?: "4x"),
            deleteCloudAfterDownload = prefs[Keys.DELETE_AFTER_DOWNLOAD] ?: true,
            removeLocationMetadata = prefs[Keys.REMOVE_LOCATION] ?: true,
        )
    }

    suspend fun setWifiOnly(value: Boolean) =
        edit { it[Keys.WIFI_ONLY] = value }

    suspend fun setDefaultMode(mode: RestorationMode) =
        edit { it[Keys.DEFAULT_MODE] = mode.wire }

    suspend fun setDefaultOutput(output: OutputSize) =
        edit { it[Keys.DEFAULT_OUTPUT] = output.wire }

    suspend fun setDeleteAfterDownload(value: Boolean) =
        edit { it[Keys.DELETE_AFTER_DOWNLOAD] = value }

    suspend fun setRemoveLocationMetadata(value: Boolean) =
        edit { it[Keys.REMOVE_LOCATION] = value }

    private suspend fun edit(block: (androidx.datastore.preferences.core.MutablePreferences) -> Unit) {
        context.dataStore.edit(block)
    }
}
