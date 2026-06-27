package com.example.photorestorer.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.navigation.NavType
import com.example.photorestorer.ui.auth.AuthScreen
import com.example.photorestorer.ui.batch.BatchReviewScreen
import com.example.photorestorer.ui.editor.EditorScreen
import com.example.photorestorer.ui.history.HistoryScreen
import com.example.photorestorer.ui.home.HomeScreen
import com.example.photorestorer.ui.result.ResultScreen
import com.example.photorestorer.ui.settings.SettingsScreen

object Routes {
    const val AUTH = "auth"
    const val HOME = "home"
    const val BATCH = "batch"
    const val HISTORY = "history"
    const val SETTINGS = "settings"
    const val RESULT = "result/{jobId}"
    const val EDITOR = "editor/{index}"

    fun result(jobId: String) = "result/$jobId"
    fun editor(index: Int) = "editor/$index"
}

@Composable
fun PhotoRestorerNavHost(
    navController: NavHostController,
    startDestination: String,
) {
    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.AUTH) {
            AuthScreen(onAuthenticated = {
                navController.navigate(Routes.HOME) {
                    popUpTo(Routes.AUTH) { inclusive = true }
                }
            })
        }
        composable(Routes.HOME) {
            HomeScreen(
                onSelectionReady = { navController.navigate(Routes.BATCH) },
                onOpenHistory = { navController.navigate(Routes.HISTORY) },
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                onOpenResult = { jobId -> navController.navigate(Routes.result(jobId)) },
            )
        }
        composable(Routes.BATCH) {
            BatchReviewScreen(
                onBack = { navController.popBackStack() },
                onEditMask = { index -> navController.navigate(Routes.editor(index)) },
                onStarted = {
                    navController.navigate(Routes.HISTORY) {
                        popUpTo(Routes.HOME)
                    }
                },
            )
        }
        composable(
            Routes.EDITOR,
            arguments = listOf(navArgument("index") { type = NavType.IntType }),
        ) {
            EditorScreen(onDone = { navController.popBackStack() })
        }
        composable(Routes.HISTORY) {
            HistoryScreen(
                onBack = { navController.popBackStack() },
                onOpenResult = { jobId -> navController.navigate(Routes.result(jobId)) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
        composable(
            Routes.RESULT,
            arguments = listOf(navArgument("jobId") { type = NavType.StringType }),
        ) { entry ->
            ResultScreen(
                jobId = entry.arguments?.getString("jobId").orEmpty(),
                onBack = { navController.popBackStack() },
            )
        }
    }
}
