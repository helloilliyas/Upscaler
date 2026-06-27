package com.example.photorestorer.repository

import com.example.photorestorer.data.model.RestorationJob
import com.example.photorestorer.data.model.toDomain
import com.example.photorestorer.database.RestorationJobDao
import com.example.photorestorer.database.RestorationJobEntity
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class HistoryRepository @Inject constructor(
    private val dao: RestorationJobDao,
) {
    val history: Flow<List<RestorationJob>> =
        dao.observeAll().map { list -> list.map { it.toDomain() } }

    fun observe(remoteJobId: String): Flow<RestorationJob?> =
        dao.observeByRemoteId(remoteJobId).map { it?.toDomain() }

    suspend fun upsert(entity: RestorationJobEntity) = dao.upsert(entity)

    suspend fun get(remoteJobId: String): RestorationJobEntity? = dao.getByRemoteId(remoteJobId)

    suspend fun update(entity: RestorationJobEntity) = dao.update(entity)

    suspend fun delete(remoteJobId: String) = dao.deleteByRemoteId(remoteJobId)

    suspend fun markCloudDeleted(remoteJobId: String) = dao.markCloudDeleted(remoteJobId)
}
