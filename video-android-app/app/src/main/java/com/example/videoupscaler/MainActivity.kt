package com.example.videoupscaler

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.example.videoupscaler.ui.VideoUpscalerTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            VideoUpscalerTheme {
                val vm: MainViewModel = viewModel()
                AppScreen(vm)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppScreen(vm: MainViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    // Refresh the short-lived ID token when the app comes up already signed in.
    LaunchedEffect(Unit) { vm.refreshTokenSilently(context) }

    Scaffold(
        topBar = {
            if (state.email != null) {
                TopAppBar(
                    title = { Text(stringResource(R.string.app_name)) },
                    actions = {
                        TextButton(onClick = { vm.signOut(context) }) {
                            Text(stringResource(R.string.sign_out))
                        }
                    },
                )
            }
        },
    ) { padding ->
        if (state.email == null) {
            SignInContent(
                busy = state.authBusy,
                error = state.authError,
                onSignIn = { vm.signIn(context) },
                modifier = Modifier.padding(padding),
            )
        } else {
            HomeContent(state, vm, modifier = Modifier.padding(padding))
        }
    }
}

@Composable
private fun SignInContent(
    busy: Boolean,
    error: String?,
    onSignIn: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            "Turn your clips into crisp, up-to-4K video.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(32.dp))
        Button(onClick = onSignIn, enabled = !busy) {
            Text(stringResource(R.string.continue_with_google))
        }
        if (error != null) {
            Spacer(Modifier.height(16.dp))
            Text(error, color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun HomeContent(
    state: UiState,
    vm: MainViewModel,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val pickVideo = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        uri?.let { vm.selectVideo(it, queryDisplayName(context, it)) }
    }
    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { vm.startUpscale() } // start either way; the notification is a nicety

    val running = state.work is WorkUi.Running

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Video", style = MaterialTheme.typography.titleMedium)
                Text(
                    state.selectedName ?: "No video selected",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(
                    enabled = !running,
                    onClick = {
                        pickVideo.launch(
                            PickVisualMediaRequest(
                                ActivityResultContracts.PickVisualMedia.VideoOnly,
                            ),
                        )
                    },
                ) {
                    Text(stringResource(R.string.select_video))
                }
            }
        }

        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Output size", style = MaterialTheme.typography.titleMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutputSize.entries.forEach { option ->
                        FilterChip(
                            selected = state.output == option,
                            enabled = !running,
                            onClick = { vm.setOutput(option) },
                            label = { Text(option.label) },
                        )
                    }
                }
            }
        }

        Button(
            enabled = state.selectedUri != null && !running,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                if (Build.VERSION.SDK_INT >= 33 &&
                    ContextCompat.checkSelfPermission(
                        context, Manifest.permission.POST_NOTIFICATIONS,
                    ) != PackageManager.PERMISSION_GRANTED
                ) {
                    notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                } else {
                    vm.startUpscale()
                }
            },
        ) {
            Text("Upscale")
        }

        when (val work = state.work) {
            is WorkUi.Idle -> Unit
            is WorkUi.Running -> ProgressCard(work)
            is WorkUi.Failed -> FailedCard(work.message, onRetry = vm::startUpscale)
            is WorkUi.Done -> ResultCard(work, onNewVideo = vm::reset)
        }
    }
}

@Composable
private fun ProgressCard(work: WorkUi.Running) {
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(work.stage, style = MaterialTheme.typography.titleMedium)
            LinearProgressIndicator(
                progress = { work.progress / 100f },
                modifier = Modifier.fillMaxWidth(),
            )
            if (work.framesTotal > 0) {
                Text(
                    "${work.framesDone} / ${work.framesTotal} frames",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun FailedCard(message: String, onRetry: () -> Unit) {
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Something went wrong", style = MaterialTheme.typography.titleMedium)
            Text(message, color = MaterialTheme.colorScheme.error)
            OutlinedButton(onClick = onRetry) { Text("Try again") }
        }
    }
}

@Composable
private fun ResultCard(work: WorkUi.Done, onNewVideo: () -> Unit) {
    val context = LocalContext.current
    Card {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Saved to Gallery", style = MaterialTheme.typography.titleMedium)
            if (work.width > 0) {
                Text("${work.width} × ${work.height}", style = MaterialTheme.typography.bodySmall)
            }
            if (work.savedUri.isNotBlank()) {
                VideoPlayer(
                    uri = Uri.parse(work.savedUri),
                    modifier = Modifier.fillMaxWidth().height(240.dp),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { shareVideo(context, work.savedUri) }) {
                    Text("Share")
                }
                Button(onClick = onNewVideo) { Text("New video") }
            }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun VideoPlayer(uri: Uri, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val player = remember(uri) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(uri))
            prepare()
        }
    }
    DisposableEffect(player) {
        onDispose { player.release() }
    }
    AndroidView(
        factory = { ctx -> PlayerView(ctx).apply { this.player = player } },
        modifier = modifier,
    )
}

private fun queryDisplayName(context: Context, uri: Uri): String? =
    context.contentResolver
        .query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }

private fun shareVideo(context: Context, savedUri: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "video/mp4"
        putExtra(Intent.EXTRA_STREAM, Uri.parse(savedUri))
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Share video"))
}
