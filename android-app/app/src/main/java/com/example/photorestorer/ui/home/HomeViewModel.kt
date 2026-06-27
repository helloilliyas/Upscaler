package com.example.photorestorer.ui.home

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.data.model.RestorationJob
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.ui.SelectionStore
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val selectionStore: SelectionStore,
    historyRepository: HistoryRepository,
) : ViewModel() {

    val recentJobs: StateFlow<List<RestorationJob>> =
        historyRepository.history
            .map { it.take(5) }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun onPhotosPicked(uris: List<Uri>) {
        selectionStore.set(uris)
    }
}
