package com.example.photorestorer.ui

import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** Maps a selected photo Uri to the repair-mask Uri drawn for it (Restore mode). */
@Singleton
class MaskStore @Inject constructor() {
    private val _masks = MutableStateFlow<Map<String, String>>(emptyMap())
    val masks: StateFlow<Map<String, String>> = _masks.asStateFlow()

    fun put(photoUri: Uri, maskUri: Uri) {
        _masks.value = _masks.value + (photoUri.toString() to maskUri.toString())
    }

    fun get(photoUri: Uri): Uri? =
        _masks.value[photoUri.toString()]?.let(Uri::parse)

    fun clear() {
        _masks.value = emptyMap()
    }
}
