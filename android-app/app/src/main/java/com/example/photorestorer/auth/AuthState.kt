package com.example.photorestorer.auth

/** Authentication state observed by the UI. */
sealed interface AuthState {
    data object Unknown : AuthState
    data object SignedOut : AuthState
    data class SignedIn(val email: String) : AuthState
    data class Error(val message: String) : AuthState
}
