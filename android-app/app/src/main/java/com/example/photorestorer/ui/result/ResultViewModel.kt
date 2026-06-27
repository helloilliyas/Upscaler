package com.example.photorestorer.ui.result

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.data.model.RestorationJob
import com.example.photorestorer.repository.HistoryRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class ResultViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    historyRepository: HistoryRepository,
) : ViewModel() {

    private val jobId: String = savedStateHandle["jobId"] ?: ""

    val job: StateFlow<RestorationJob?> =
        historyRepository.observe(jobId)
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
}
