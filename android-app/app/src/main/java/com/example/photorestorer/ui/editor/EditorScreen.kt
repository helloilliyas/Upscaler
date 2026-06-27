package com.example.photorestorer.ui.editor

import android.graphics.Paint
import android.graphics.Path
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.Canvas
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.photorestorer.util.NormPoint

private val REPAIR_TINT = android.graphics.Color.argb(120, 229, 57, 53)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditorScreen(
    onDone: () -> Unit,
    viewModel: EditorViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Repair brush") },
                navigationIcon = {
                    IconButton(onClick = onDone) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    TextButton(
                        onClick = { viewModel.save(onDone) },
                        enabled = !state.saving,
                    ) {
                        Text(if (state.hasMask) "Save mask" else "Done")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "Paint over scratches or damage to repair. Black is kept; painted areas are repaired.",
                style = MaterialTheme.typography.bodySmall,
            )

            val bitmap = state.bitmap
            val size = state.imageSize
            when {
                state.loading -> Box(
                    Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }

                bitmap == null || size == null -> Box(
                    Modifier.fillMaxWidth().weight(1f),
                    contentAlignment = Alignment.Center,
                ) { Text("Could not load this photo.") }

                else -> Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center,
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(size.width.toFloat() / size.height.toFloat())
                            .background(Color.Black)
                            .pointerInput(Unit) {
                                detectDragGestures(
                                    onDragStart = { offset ->
                                        viewModel.startStroke(
                                            (offset.x / this.size.width).coerceIn(0f, 1f),
                                            (offset.y / this.size.height).coerceIn(0f, 1f),
                                        )
                                    },
                                    onDrag = { change, _ ->
                                        val p = change.position
                                        viewModel.extendStroke(
                                            (p.x / this.size.width).coerceIn(0f, 1f),
                                            (p.y / this.size.height).coerceIn(0f, 1f),
                                        )
                                    },
                                    onDragEnd = { viewModel.endStroke() },
                                )
                            },
                    ) {
                        Image(
                            bitmap = bitmap,
                            contentDescription = "Photo",
                            contentScale = ContentScale.FillBounds,
                            modifier = Modifier.fillMaxSize(),
                        )
                        MaskOverlay(
                            strokes = state.strokes,
                            current = state.current,
                            currentWidthFraction = state.brushWidthFraction,
                            currentErase = state.eraser,
                        )
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                FilterChip(
                    selected = state.eraser,
                    onClick = { viewModel.setEraser(!state.eraser) },
                    label = { Text("Eraser") },
                )
                IconButton(onClick = viewModel::undo, enabled = state.canUndo) {
                    Icon(Icons.AutoMirrored.Filled.Undo, contentDescription = "Undo")
                }
                TextButton(onClick = viewModel::clear, enabled = state.canUndo) {
                    Text("Clear")
                }
            }
            Text("Brush size", style = MaterialTheme.typography.labelMedium)
            Slider(
                value = state.brushWidthFraction,
                onValueChange = viewModel::setBrushWidth,
                valueRange = 0.01f..0.15f,
            )
        }
    }
}

@Composable
private fun MaskOverlay(
    strokes: List<com.example.photorestorer.util.MaskStroke>,
    current: List<NormPoint>,
    currentWidthFraction: Float,
    currentErase: Boolean,
) {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val w = size.width
        val h = size.height
        drawIntoCanvas { canvas ->
            val native = canvas.nativeCanvas
            val layer = native.saveLayer(0f, 0f, w, h, null)
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                style = Paint.Style.STROKE
                strokeCap = Paint.Cap.ROUND
                strokeJoin = Paint.Join.ROUND
            }
            val clearMode = PorterDuffXfermode(PorterDuff.Mode.CLEAR)

            fun render(points: List<NormPoint>, widthFraction: Float, erase: Boolean) {
                if (points.isEmpty()) return
                paint.strokeWidth = widthFraction * w
                if (erase) {
                    paint.xfermode = clearMode
                } else {
                    paint.xfermode = null
                    paint.color = REPAIR_TINT
                }
                if (points.size == 1) {
                    native.drawPoint(points[0].x * w, points[0].y * h, paint)
                    return
                }
                val path = Path()
                path.moveTo(points[0].x * w, points[0].y * h)
                for (i in 1 until points.size) {
                    path.lineTo(points[i].x * w, points[i].y * h)
                }
                native.drawPath(path, paint)
            }

            strokes.forEach { render(it.points, it.widthFraction, it.erase) }
            if (current.isNotEmpty()) render(current, currentWidthFraction, currentErase)
            native.restoreToCount(layer)
        }
    }
}
