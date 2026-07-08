package com.example.photorestorer.ui.batch

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun BatchReviewScreen(
    onBack: () -> Unit,
    onEditMask: (Int) -> Unit,
    onStarted: () -> Unit,
    viewModel: BatchViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Review (${state.photos.size})") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Mode", style = MaterialTheme.typography.titleSmall)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                RestorationMode.entries.forEach { mode ->
                    FilterChip(
                        selected = state.mode == mode,
                        onClick = { viewModel.setMode(mode) },
                        label = { Text(mode.label) },
                    )
                }
            }

            Text("Output", style = MaterialTheme.typography.titleSmall)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutputSize.entries.forEach { output ->
                    FilterChip(
                        selected = state.output == output,
                        onClick = { viewModel.setOutput(output) },
                        label = { Text(output.label) },
                    )
                }
            }

            if (state.mode != RestorationMode.ULTRA) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Strength", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "${(state.strength * 100).roundToInt()}%",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                Slider(
                    value = state.strength,
                    onValueChange = viewModel::setStrength,
                    valueRange = 0f..1f,
                )
                Text(
                    "Lower for a gentler, more natural result; 100% applies the full effect.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Switch(checked = state.wifiOnly, onCheckedChange = viewModel::setWifiOnly)
                Text("  Wi-Fi only", style = MaterialTheme.typography.bodyMedium)
            }

            if (state.mode == RestorationMode.ULTRA) {
                Text(
                    "Ultra Detail reconstructs fine textures using generative AI and runs " +
                        "one job at a time. Some details may look realistic but may not match " +
                        "the original exactly.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            }

            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                itemsIndexed(state.photos, key = { _, uri -> uri.toString() }) { index, uri ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AsyncImage(
                            model = uri,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(56.dp).padding(end = 12.dp),
                        )
                        Text(
                            uri.lastPathSegment ?: uri.toString(),
                            modifier = Modifier.weight(1f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (state.mode == RestorationMode.RESTORE) {
                            val masked = state.maskedPhotos.contains(uri.toString())
                            TextButton(onClick = { onEditMask(index) }) {
                                Text(
                                    if (masked) "Mask ✓" else "Add mask",
                                    color = if (masked) {
                                        MaterialTheme.colorScheme.tertiary
                                    } else {
                                        MaterialTheme.colorScheme.primary
                                    },
                                )
                            }
                        }
                        TextButton(onClick = { viewModel.removePhoto(uri) }) { Text("Remove") }
                    }
                }
            }

            Button(
                onClick = { viewModel.start(onStarted) },
                enabled = state.photos.isNotEmpty(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Start")
            }
        }
    }
}
