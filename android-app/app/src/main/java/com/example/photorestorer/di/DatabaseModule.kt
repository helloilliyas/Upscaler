package com.example.photorestorer.di

import android.content.Context
import androidx.room.Room
import com.example.photorestorer.database.AppDatabase
import com.example.photorestorer.database.RestorationJobDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, AppDatabase.NAME)
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideRestorationJobDao(database: AppDatabase): RestorationJobDao =
        database.restorationJobDao()
}
