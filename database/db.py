import asyncpg


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn, ssl="require")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def init_tables(self):
        async with self.pool.acquire() as conn:

            # Пользователи
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                fullname TEXT,
                phone TEXT,
                username TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')
            )
            """)

            # Каталог
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')
            )
            """)

            # Готовые работы
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id SERIAL PRIMARY KEY,
                file_id TEXT,
                vk_file_id TEXT,
                media_type TEXT,
                vk_media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            await conn.execute("ALTER TABLE works ADD COLUMN IF NOT EXISTS vk_file_id TEXT")
            await conn.execute("ALTER TABLE works ADD COLUMN IF NOT EXISTS vk_media_type TEXT")

            # Отзывы
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                text TEXT,
                file_id TEXT,
                vk_file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            await conn.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vk_file_id TEXT")

            # Заказы
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                fullname TEXT,
                phone_number TEXT,
                account TEXT,
                cake TEXT,
                size TEXT,
                date_delivery TEXT,
                media TEXT,
                logistics TEXT,
                additional_info TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

    # ================= USERS =================

    async def add_user(self, telegram_id, fullname, phone=None, username=None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
            INSERT INTO users (
                telegram_id,
                fullname,
                phone,
                username
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
                               telegram_id,
                               fullname,
                               phone,
                               username
                               )

    async def get_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM users
                ORDER BY created_at DESC
            """)

    # ================= ORDERS =================

    async def add_order(self, telegram_id, data):
        async with self.pool.acquire() as conn:
            await conn.execute("""
            INSERT INTO orders (
                user_id,
                fullname,
                phone_number,
                account,
                cake,
                size,
                date_delivery,
                logistics,
                media,
                additional_info
            )
            VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10
            )
            """,
                               telegram_id,
                               data.get("fullname"),
                               data.get("phone_number"),
                               data.get("account"),
                               data.get("cake"),
                               data.get("size"),
                               data.get("date_delivery"),
                               data.get("logistics"),
                               data.get("media"),
                               data.get("additional_info")
                               )

    async def get_orders(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM orders
                ORDER BY created_at DESC
            """)

    # ================= CATALOG =================

    async def get_catalog(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM catalog
                ORDER BY created_at DESC
            """)

    async def get_product(self, product_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT *
                FROM catalog
                WHERE id = $1
            """, product_id)

    # ================= WORKS =================

    async def get_works(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM works
                ORDER BY created_at DESC
            """)

    # ================= REVIEWS =================

    async def get_reviews(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM reviews
                ORDER BY created_at DESC
            """)

    async def count_orders_by_date(self, date_str: str) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*)
                FROM orders
                WHERE date_delivery = $1
            """, date_str)
