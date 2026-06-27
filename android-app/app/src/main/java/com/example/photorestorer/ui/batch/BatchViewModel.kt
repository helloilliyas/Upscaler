package com.example.photorestorer.ui.batch

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.data.SettingsRepository
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import com.example.photorestorer.ui.MaskStore
import com.example.photorestorer.ui.SelectionStore
import com.example.photorestorer.worker.RestorationRequest
import com.example.photorestorer.worker.RestorationScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

data class BatchUiState(
    val photos: List<Uri> = emptyList(),
    val mode: RestorationMode = RestorationMode.NATURAL,
    val output: OutputSize = OutputSize.X4,
    val wifiOnly: Boolean = false,
    val maskedPhotos: Set<String> = emptySet(),
)

@HiltViewModel
class BatchViewModel @Inject constructor(
    private val selectionStore: SelectionStore,
    private val settingsRepository: SettingsRepository,
    private val maskStore: MaskStore,
    private val scheduler: RestorationScheduler,
) : ViewModel() {

    private val _uiState = MutableStateFlow(BatchUiState())
    val uiState: StateFlow<BatchUiState> = _uiState.asStateFlow()

    init {
        _uiState.update { it.copy(photos = selectionStore.selected.value) }
        viewModelScope.launch {
            val settings = settingsRepository.settings.first()
            _uiState.update {
                it.copy(
                    mode = settings.defaultMode,
                    output = settings.defaultOutput,
                    wifiOnly = settings.wifiOnly,
                )
            }
        }
        // Reflect masks drawn in the editor (which writes to MaskStore).
        viewModelScope.launch {
            maskStore.masks.collect { masks ->
                _uiState.update { it.copy(maskedPhotos = masks.keys) }
            }
        }
    }

    fun setMode(mode: RestorationMode) = _uiState.update { it.copy(mode = mode) }
    fun setOutput(output: OutputSize) = _uiState.update { it.copy(output = output) }
    fun setWifiOnly(value: Boolean) = _uiState.update { it.copy(wifiOnly = value) }

    fun removePhoto(uri: Uri) {
        selectionStore.remove(uri)
        _uiState.update { it.copy(photos = selectionStore.selected.value) }
    }

    fun start(onStarted: () -> Unit) {
        val state = _uiState.value
        if (state.photos.isEmpty()) return
        viewModelScope.launch {
            val settings = settingsRepository.settings.first()
            state.photos.forEach { uri ->
                // Masks only apply to Restore mode.
                val maskUri = if (state.mode == RestorationMode.RESTORE) {
                    maskStore.get(uri)?.toString()
                } else {
                    null
                }
                scheduler.enqueue(
                    RestorationRequest(
                        photoUri = uri.toString(),
                        maskUri = maskUri,
                        mode = state.mode,
                        output = state.output,
                        preserveMetadata = !settings.removeLocationMetadata,
                        idempotencyKey = UUID.randomUUID().toString(),
                        wifiOnly = state.wifiOnly,
                        deleteAfterDownload = settings.deleteCloudAfterDownload,
                    ),
                )
            }
            selectionStore.clear()
            maskStore.clear()
            onStarted()
        }
    }
}
