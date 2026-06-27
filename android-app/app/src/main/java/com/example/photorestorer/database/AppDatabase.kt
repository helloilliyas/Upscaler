package com.example.photorestorer.database

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [RestorationJobEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun restorationJobDao(): RestorationJobDao

    companion object {
        const val NAME = "photo_restorer.db"
    }
}
