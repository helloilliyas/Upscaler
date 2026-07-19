package com.example.videoupscaler

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.example.videoupscaler.auth.SignInResult
import com.example.videoupscaler.work.UpscaleWorker
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Presentation of the (at most one) upscale job. */
sealed interface WorkUi {
    data object Idle : WorkUi
    data class Running(
        val progress: Int,
        val stage: String,
        val framesDone: Int,
        val framesTotal: Int,
    ) : WorkUi

    data class Done(val savedUri: String, val width: Int, val height: Int) : WorkUi
    data class Failed(val message: String) : WorkUi
}

data class UiState(
    val email: String? = null,
    val selectedUri: String? = null,
    val selectedName: String? = null,
    val output: OutputSize = OutputSize.X2,
    val authBusy: Boolean = false,
    val authError: String? = null,
    val work: WorkUi = WorkUi.Idle,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val workManager = WorkManager.getInstance(application)
    private val local = MutableStateFlow(
        UiState(email = ServiceLocator.tokenStore.currentEmail()),
    )

    val state: StateFlow<UiState> = combine(
        local,
        workManager.getWorkInfosForUniqueWorkFlow(UpscaleWorker.UNIQUE_NAME),
    ) { ui, infos ->
        ui.copy(work = toWorkUi(infos))
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), local.value)

    // --- auth ------------------------------------------------------------

    /** Interactive sign-in; must be called with an Activity context. */
    fun signIn(activityContext: Context) {
        local.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            when (val result = ServiceLocator.authManager.signIn(activityContext)) {
                is SignInResult.Success ->
                    local.update { it.copy(email = result.email, authBusy = false) }
                is SignInResult.Failure ->
                    local.update { it.copy(authBusy = false, authError = result.message) }
            }
        }
    }

    /** Silently refresh the short-lived ID token for an already-approved account. */
    fun refreshTokenSilently(activityContext: Context) {
        if (local.value.email == null) return
        viewModelScope.launch {
            ServiceLocator.authManager.signIn(activityContext, filterByAuthorizedAccounts = true)
        }
    }

    fun signOut(activityContext: Context) {
        viewModelScope.launch {
            ServiceLocator.authManager.signOut(activityContext)
            workManager.cancelUniqueWork(UpscaleWorker.UNIQUE_NAME)
            local.update { UiState() }
        }
    }

    // --- selection / job -------------------------------------------------

    fun selectVideo(uri: Uri, displayName: String?) {
        workManager.pruneWork() // clear any finished job from the flow
        local.update { it.copy(selectedUri = uri.toString(), selectedName = displayName) }
    }

    fun setOutput(output: OutputSize) {
        local.update { it.copy(output = output) }
    }

    fun startUpscale() {
        val current = local.value
        val uri = current.selectedUri ?: return
        val request = OneTimeWorkRequestBuilder<UpscaleWorker>()
            .setInputData(
                workDataOf(
                    UpscaleWorker.KEY_URI to uri,
                    UpscaleWorker.KEY_OUTPUT to current.output.apiValue,
                    // Fixed per enqueue: a network retry reattaches to the same
                    // server-side job instead of paying for a second one.
                    UpscaleWorker.KEY_IDEMPOTENCY to UUID.randomUUID().toString(),
                ),
            )
            .setConstraints(
                Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build(),
            )
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
            .build()
        workManager.enqueueUniqueWork(UpscaleWorker.UNIQUE_NAME, ExistingWorkPolicy.REPLACE, request)
    }

    fun reset() {
        workManager.pruneWork()
        local.update { it.copy(selectedUri = null, selectedName = null) }
    }

    // --- internals --------------------------------------------------------

    private fun toWorkUi(infos: List<WorkInfo>): WorkUi {
        val info = infos.firstOrNull() ?: return WorkUi.Idle
        return when (info.state) {
            WorkInfo.State.ENQUEUED, WorkInfo.State.BLOCKED ->
                WorkUi.Running(0, "Waiting for network", 0, 0)
            WorkInfo.State.RUNNING -> WorkUi.Running(
                progress = info.progress.getInt(UpscaleWorker.KEY_PROGRESS, 0),
                stage = info.progress.getString(UpscaleWorker.KEY_STAGE) ?: "Processing",
                framesDone = info.progress.getInt(UpscaleWorker.KEY_FRAMES_DONE, 0),
                framesTotal = info.progress.getInt(UpscaleWorker.KEY_FRAMES_TOTAL, 0),
            )
            WorkInfo.State.SUCCEEDED -> WorkUi.Done(
                savedUri = info.outputData.getString(UpscaleWorker.KEY_SAVED_URI).orEmpty(),
                width = info.outputData.getInt(UpscaleWorker.KEY_WIDTH, 0),
                height = info.outputData.getInt(UpscaleWorker.KEY_HEIGHT, 0),
            )
            WorkInfo.State.FAILED -> WorkUi.Failed(
                info.outputData.getString(UpscaleWorker.KEY_ERROR) ?: "Processing failed",
            )
            WorkInfo.State.CANCELLED -> WorkUi.Idle
        }
    }
}
