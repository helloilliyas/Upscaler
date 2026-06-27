package com.example.photorestorer.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.data.model.RestorationJob
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.repository.RestorationRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val historyRepository: HistoryRepository,
    private val restorationRepository: RestorationRepository,
) : ViewModel() {

    val history: StateFlow<List<RestorationJob>> =
        historyRepository.history
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun deleteJob(remoteJobId: String) {
        viewModelScope.launch {
            runCatching { restorationRepository.deleteRemoteJob(remoteJobId) }
            historyRepository.delete(remoteJobId)
        }
    }
}
