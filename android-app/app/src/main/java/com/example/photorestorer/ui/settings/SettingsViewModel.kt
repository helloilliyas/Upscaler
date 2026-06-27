package com.example.photorestorer.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.data.AppSettings
import com.example.photorestorer.data.SettingsRepository
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import com.example.photorestorer.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val authRepository: AuthRepository,
) : ViewModel() {

    val settings: StateFlow<AppSettings> =
        settingsRepository.settings
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AppSettings())

    fun setWifiOnly(value: Boolean) = launch { settingsRepository.setWifiOnly(value) }
    fun setDefaultMode(mode: RestorationMode) = launch { settingsRepository.setDefaultMode(mode) }
    fun setDefaultOutput(output: OutputSize) = launch { settingsRepository.setDefaultOutput(output) }
    fun setDeleteAfterDownload(value: Boolean) =
        launch { settingsRepository.setDeleteAfterDownload(value) }
    fun setRemoveLocation(value: Boolean) =
        launch { settingsRepository.setRemoveLocationMetadata(value) }

    fun signOut(onDone: () -> Unit) = launch {
        authRepository.signOut()
        onDone()
    }

    private fun launch(block: suspend () -> Unit) {
        viewModelScope.launch { block() }
    }
}
