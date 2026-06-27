package com.example.photorestorer.ui.auth

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.photorestorer.auth.AuthState
import com.example.photorestorer.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<AuthState>(AuthState.Unknown)
    val state: StateFlow<AuthState> = _state.asStateFlow()

    private val _signingIn = MutableStateFlow(false)
    val signingIn: StateFlow<Boolean> = _signingIn.asStateFlow()

    /** Attempt a quiet sign-in with a previously authorized account. */
    fun trySilentSignIn(context: Context) {
        if (_signingIn.value) return
        viewModelScope.launch {
            _signingIn.value = true
            val result = authRepository.signIn(context, filterByAuthorizedAccounts = true)
            // Silent failure just means the user must tap the button.
            _state.value = if (result is AuthState.SignedIn) result else AuthState.SignedOut
            _signingIn.value = false
        }
    }

    fun signIn(context: Context) {
        if (_signingIn.value) return
        viewModelScope.launch {
            _signingIn.value = true
            _state.value = authRepository.signIn(context, filterByAuthorizedAccounts = false)
            _signingIn.value = false
        }
    }
}
