package com.example.photorestorer.auth

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialException
import com.example.photorestorer.BuildConfig
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import javax.inject.Inject
import javax.inject.Singleton

/** Result of a sign-in attempt. */
sealed interface SignInResult {
    data class Success(val email: String, val idToken: String) : SignInResult
    data class Failure(val message: String) : SignInResult
}

/**
 * Wraps Android Credential Manager + Sign in with Google.
 *
 * Requests a Google **ID token** for the Web client id audience (the same value
 * the backend verifies). The token is cached in [TokenStore] for the OkHttp
 * interceptor. No Gmail/Drive scopes are requested and no password is stored.
 */
@Singleton
class GoogleAuthManager @Inject constructor(
    private val credentialManager: CredentialManager,
    private val tokenStore: TokenStore,
) {

    /**
     * Trigger the credential flow. Must be called with an Activity [context].
     *
     * @param filterByAuthorizedAccounts when true, only previously-authorized
     *   accounts are offered (silent-ish); fall back to false to let the user
     *   pick a new account.
     */
    suspend fun signIn(
        context: Context,
        filterByAuthorizedAccounts: Boolean = false,
    ): SignInResult {
        if (BuildConfig.GOOGLE_WEB_CLIENT_ID.isBlank()) {
            return SignInResult.Failure(
                "Google Web client id is not configured for this build.",
            )
        }

        val option = GetGoogleIdOption.Builder()
            .setServerClientId(BuildConfig.GOOGLE_WEB_CLIENT_ID)
            .setFilterByAuthorizedAccounts(filterByAuthorizedAccounts)
            .setAutoSelectEnabled(filterByAuthorizedAccounts)
            .build()

        val request = GetCredentialRequest.Builder()
            .addCredentialOption(option)
            .build()

        return try {
            val response = credentialManager.getCredential(context, request)
            val credential = response.credential
            if (credential is androidx.credentials.CustomCredential &&
                credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
            ) {
                val googleCredential = GoogleIdTokenCredential.createFrom(credential.data)
                tokenStore.update(googleCredential.idToken)
                SignInResult.Success(
                    email = googleCredential.id,
                    idToken = googleCredential.idToken,
                )
            } else {
                SignInResult.Failure("Unexpected credential type.")
            }
        } catch (e: GetCredentialException) {
            SignInResult.Failure(e.message ?: "Sign-in was cancelled or failed.")
        } catch (e: GoogleIdTokenParsingException) {
            SignInResult.Failure("Could not read the Google ID token.")
        }
    }

    suspend fun signOut() {
        tokenStore.clear()
        try {
            credentialManager.clearCredentialState(
                androidx.credentials.ClearCredentialStateRequest(),
            )
        } catch (_: Exception) {
            // Clearing local credential state is best-effort.
        }
    }
}
