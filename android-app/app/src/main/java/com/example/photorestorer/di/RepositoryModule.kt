package com.example.photorestorer.di

import com.example.photorestorer.repository.RestorationRepository
import com.example.photorestorer.repository.RestorationRepositoryImpl
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindRestorationRepository(
        impl: RestorationRepositoryImpl,
    ): RestorationRepository
}
