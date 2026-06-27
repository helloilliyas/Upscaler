package com.example.photorestorer.repository

import android.content.Context
import com.example.photorestorer.auth.AuthState
import com.example.photorestorer.auth.GoogleAuthManager
import com.example.photorestorer.auth.SignInResult
import com.example.photorestorer.auth.TokenStore
import com.example.photorestorer.network.RestorationApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val googleAuthManager: GoogleAuthManager,
    private val api: RestorationApi,
    private val tokenStore: TokenStore,
) {
    private val _state = MutableStateFlow<AuthState>(AuthState.Unknown)
    val state: StateFlow<AuthState> = _state.asStateFlow()

    /**
     * Run the credential flow, then confirm with the backend that this is the
     * approved account. A 403 means a valid Google account that is not allowed.
     */
    suspend fun signIn(context: Context, filterByAuthorizedAccounts: Boolean): AuthState {
        when (val result = googleAuthManager.signIn(context, filterByAuthorizedAccounts)) {
            is SignInResult.Failure -> {
                _state.value = AuthState.Error(result.message)
            }
            is SignInResult.Success -> {
                _state.value = confirmWithBackend(result.email)
            }
        }
        return _state.value
    }

    private suspend fun confirmWithBackend(email: String): AuthState {
        return try {
            val response = api.me()
            when {
                response.isSuccessful && response.body()?.authorized == true ->
                    AuthState.SignedIn(response.body()!!.email)
                response.code() == 403 -> {
                    tokenStore.clear()
                    AuthState.Error("This Google account is not approved for the app.")
                }
                response.code() == 401 -> {
                    tokenStore.clear()
                    AuthState.Error("Sign-in expired. Please try again.")
                }
                else -> AuthState.Error("Could not verify the account (${response.code()}).")
            }
        } catch (e: Exception) {
            AuthState.Error(e.message ?: "Network error during sign-in.")
        }
    }

    suspend fun signOut() {
        googleAuthManager.signOut()
        _state.value = AuthState.SignedOut
    }

    fun hasToken(): Boolean = tokenStore.current() != null
}
