package com.example.photorestorer.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface RestorationJobDao {

    @Query("SELECT * FROM restoration_jobs ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<RestorationJobEntity>>

    @Query("SELECT * FROM restoration_jobs WHERE remoteJobId = :remoteJobId LIMIT 1")
    fun observeByRemoteId(remoteJobId: String): Flow<RestorationJobEntity?>

    @Query("SELECT * FROM restoration_jobs WHERE remoteJobId = :remoteJobId LIMIT 1")
    suspend fun getByRemoteId(remoteJobId: String): RestorationJobEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: RestorationJobEntity): Long

    @Update
    suspend fun update(entity: RestorationJobEntity)

    @Query("DELETE FROM restoration_jobs WHERE remoteJobId = :remoteJobId")
    suspend fun deleteByRemoteId(remoteJobId: String)

    @Query("UPDATE restoration_jobs SET cloudDeleted = 1 WHERE remoteJobId = :remoteJobId")
    suspend fun markCloudDeleted(remoteJobId: String)
}
