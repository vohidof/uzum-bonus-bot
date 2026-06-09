import aiosqlite

async def init_db():
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT)")
        await db.commit()

async def set_lang(user_id, lang):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, lang) VALUES (?, ?)", (user_id, lang))
        await db.commit()

async def get_lang(user_id):
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 'ru'
