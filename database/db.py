import asyncpg
from pathlib import Path
from urllib.parse import urlsplit


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        host = urlsplit(self.dsn).hostname
        ssl = False if host in ("localhost", "127.0.0.1", "::1") else "require"
        self.pool = await asyncpg.create_pool(self.dsn, ssl=ssl)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def init_tables(self):
        async with self.pool.acquire() as conn, conn.transaction():
            # Два бота могут одновременно запускаться с одной базой.
            await conn.execute("SELECT pg_advisory_xact_lock(724019301)")
            # Пользователи
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                fullname TEXT,
                phone TEXT,
                username TEXT,
                personal_data_consent BOOLEAN DEFAULT FALSE,
                personal_data_consent_at TIMESTAMP WITH TIME ZONE,
                personal_data_consent_platform TEXT,
                personal_data_consent_document TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')
            )
            """)
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent BOOLEAN DEFAULT FALSE")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent_at TIMESTAMP WITH TIME ZONE")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent_platform TEXT")
            await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent_document TEXT")

            # Каталог
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                file_id TEXT,
                vk_file_id TEXT,
                media_type TEXT,
                vk_media_type TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')
            )
            """)
            await conn.execute("ALTER TABLE catalog ADD COLUMN IF NOT EXISTS vk_file_id TEXT")
            await conn.execute("ALTER TABLE catalog ADD COLUMN IF NOT EXISTS vk_media_type TEXT")

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
                vk_media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            await conn.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vk_file_id TEXT")
            await conn.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vk_media_type TEXT")

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

            migration = Path(__file__).with_name("migrations") / "001_vk_identity.sql"
            await conn.execute(migration.read_text(encoding="utf-8"))

    # ================= USERS =================

    @staticmethod
    def _identity(telegram_id=None, vk_id=None):
        if (telegram_id is None) == (vk_id is None):
            raise ValueError("Provide exactly one of telegram_id or vk_id")
        value = telegram_id if telegram_id is not None else vk_id
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("Platform user ID must be a positive integer")
        return ("telegram_id" if telegram_id is not None else "vk_id"), value

    async def add_user(self, telegram_id=None, fullname=None, phone=None, username=None, *, vk_id=None):
        column, user_id = self._identity(telegram_id, vk_id)
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
            INSERT INTO users (
                {column},
                fullname,
                phone,
                username
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT ({column}) DO NOTHING
            """,
                               user_id,
                               fullname,
                               phone,
                               username
                               )

    async def has_personal_data_consent(self, telegram_id=None, *, vk_id=None) -> bool:
        column, user_id = self._identity(telegram_id, vk_id)
        async with self.pool.acquire() as conn:
            return bool(await conn.fetchval(f"""
                SELECT personal_data_consent
                FROM users
                WHERE {column} = $1
            """, user_id))

    async def set_personal_data_consent(
        self,
        telegram_id: int | None = None,
        fullname: str | None = None,
        username: str | None = None,
        platform: str | None = None,
        document: str | None = None,
        *,
        vk_id: int | None = None,
    ):
        column, user_id = self._identity(telegram_id, vk_id)
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO users (
                    {column},
                    fullname,
                    username,
                    personal_data_consent,
                    personal_data_consent_at,
                    personal_data_consent_platform,
                    personal_data_consent_document
                )
                VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP, $4, $5)
                ON CONFLICT ({column}) DO UPDATE SET
                    fullname = COALESCE(EXCLUDED.fullname, users.fullname),
                    username = COALESCE(EXCLUDED.username, users.username),
                    personal_data_consent = TRUE,
                    personal_data_consent_at = CURRENT_TIMESTAMP,
                    personal_data_consent_platform = EXCLUDED.personal_data_consent_platform,
                    personal_data_consent_document = EXCLUDED.personal_data_consent_document
            """, user_id, fullname, username, platform, document)

    async def get_users(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM users
                ORDER BY created_at DESC
            """)

    # ================= ORDERS =================

    async def add_order(self, telegram_id=None, data=None, *, vk_id=None):
        column, user_id = self._identity(telegram_id, vk_id)
        order_column = "user_id" if column == "telegram_id" else "vk_id"
        if data is None:
            raise ValueError("Order data is required")
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
            INSERT INTO orders (
                {order_column},
                fullname,
                phone_number,
                account,
                cake,
                size,
                date_delivery,
                logistics,
                media,
                additional_info,
                vk_file_id,
                vk_media_type
            )
            VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12
            )
            """,
                               user_id,
                               data.get("fullname"),
                               data.get("phone_number"),
                               data.get("account"),
                               data.get("cake"),
                               data.get("size"),
                               data.get("date_delivery"),
                               data.get("logistics"),
                               data.get("media") if vk_id is None else None,
                               data.get("additional_info"),
                               data.get("media") if vk_id is not None else None,
                               data.get("media_type") if vk_id is not None else None
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
                WHERE title IS NOT NULL
                ORDER BY created_at DESC
            """)

    async def get_product(self, product_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT *
                FROM catalog
                WHERE id = $1
                  AND title IS NOT NULL
            """, product_id)

    # ================= WORKS =================

    async def get_works(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM works
                ORDER BY created_at DESC, id DESC
            """)

    # ================= REVIEWS =================

    async def get_reviews(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM reviews
                ORDER BY created_at DESC, id DESC
            """)

    async def count_orders_by_date(self, date_str: str) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*)
                FROM orders
                WHERE date_delivery = $1
            """, date_str)
