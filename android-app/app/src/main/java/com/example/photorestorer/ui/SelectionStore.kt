package com.example.photorestorer.ui

import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** Holds the photos selected on Home until they are submitted from Batch review. */
@Singleton
class SelectionStore @Inject constructor() {
    private val _selected = MutableStateFlow<List<Uri>>(emptyList())
    val selected: StateFlow<List<Uri>> = _selected.asStateFlow()

    fun set(uris: List<Uri>) {
        _selected.value = uris.take(MAX_PHOTOS)
    }

    fun remove(uri: Uri) {
        _selected.value = _selected.value.filterNot { it == uri }
    }

    fun clear() {
        _selected.value = emptyList()
    }

    companion object {
        const val MAX_PHOTOS = 50
    }
}
