package com.example.photorestorer.ui.editor

import android.content.Context
import android.net.Uri
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.ui.MaskStore
import com.example.photorestorer.ui.SelectionStore
import com.example.photorestorer.util.ImageSize
import com.example.photorestorer.util.MaskStroke
import com.example.photorestorer.util.MaskWriter
import com.example.photorestorer.util.NormPoint
import com.example.photorestorer.util.OrientedImage
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

data class EditorUiState(
    val bitmap: ImageBitmap? = null,
    val imageSize: ImageSize? = null,
    val strokes: List<MaskStroke> = emptyList(),
    val current: List<NormPoint> = emptyList(),
    val brushWidthFraction: Float = 0.05f,
    val eraser: Boolean = false,
    val loading: Boolean = true,
    val saving: Boolean = false,
) {
    val canUndo: Boolean get() = strokes.isNotEmpty()
    val hasMask: Boolean get() = strokes.isNotEmpty()
}

private const val DISPLAY_MAX_EDGE = 2048

@HiltViewModel
class EditorViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val selectionStore: SelectionStore,
    private val maskStore: MaskStore,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val index: Int = savedStateHandle["index"] ?: 0
    private val photoUri: Uri? = selectionStore.selected.value.getOrNull(index)

    private val _uiState = MutableStateFlow(EditorUiState())
    val uiState: StateFlow<EditorUiState> = _uiState.asStateFlow()

    init {
        val uri = photoUri
        if (uri == null) {
            _uiState.update { it.copy(loading = false) }
        } else {
            viewModelScope.launch {
                val photo = withContext(Dispatchers.IO) {
                    OrientedImage.load(context, uri, DISPLAY_MAX_EDGE)
                }
                _uiState.update {
                    it.copy(
                        bitmap = photo?.bitmap?.asImageBitmap(),
                        imageSize = photo?.fullSize,
                        loading = false,
                    )
                }
            }
        }
    }

    fun startStroke(x: Float, y: Float) {
        _uiState.update { it.copy(current = listOf(NormPoint(x, y))) }
    }

    fun extendStroke(x: Float, y: Float) {
        _uiState.update { it.copy(current = it.current + NormPoint(x, y)) }
    }

    fun endStroke() {
        _uiState.update { state ->
            if (state.current.isEmpty()) {
                state
            } else {
                state.copy(
                    strokes = state.strokes + MaskStroke(
                        points = state.current,
                        widthFraction = state.brushWidthFraction,
                        erase = state.eraser,
                    ),
                    current = emptyList(),
                )
            }
        }
    }

    fun setBrushWidth(fraction: Float) {
        _uiState.update { it.copy(brushWidthFraction = fraction.coerceIn(0.01f, 0.15f)) }
    }

    fun setEraser(eraser: Boolean) {
        _uiState.update { it.copy(eraser = eraser) }
    }

    fun undo() {
        _uiState.update { it.copy(strokes = it.strokes.dropLast(1)) }
    }

    fun clear() {
        _uiState.update { it.copy(strokes = emptyList(), current = emptyList()) }
    }

    fun save(onSaved: () -> Unit) {
        val uri = photoUri
        val size = _uiState.value.imageSize
        val strokes = _uiState.value.strokes
        if (uri == null || size == null || strokes.isEmpty()) {
            onSaved()
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(saving = true) }
            val maskUri = withContext(Dispatchers.IO) {
                MaskWriter.write(context, strokes, size)
            }
            maskStore.put(uri, maskUri)
            _uiState.update { it.copy(saving = false) }
            onSaved()
        }
    }
}
