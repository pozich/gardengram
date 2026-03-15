import aiosqlite
import json

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                nick TEXT NOT NULL,
                state TEXT DEFAULT 'registration',
                grid TEXT DEFAULT '[]',
                inventory TEXT DEFAULT '{}',
                tutorial_step INTEGER DEFAULT 0,
                money INTEGER DEFAULT 100,
                cursor_pos INTEGER DEFAULT 0,
                last_spawn_time REAL DEFAULT 0,
                selected_item TEXT DEFAULT NULL
            )
        ''')
        await db.commit()

