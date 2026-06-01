"""
Database connection management and table initialization.
"""
import asyncpg


class Database:
    """Main database class for connection management and initialization."""

    def __init__(self, dsn: str):
        """
        Initialize database with connection string.

        Args:
            dsn: Database connection string
        """
        self.dsn = dsn
        self.pool = None

    async def connect(self) -> None:
        """Establish connection pool to database."""
        self.pool = await asyncpg.create_pool(self.dsn, ssl="require")

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()

    async def init_tables(self) -> None:
        """Initialize all database tables."""
        async with self.pool.acquire() as conn:
            await self._create_users_table(conn)
            await self._create_catalog_table(conn)
            await self._create_works_table(conn)
            await self._create_reviews_table(conn)
            await self._create_orders_table(conn)

    @staticmethod
    async def _create_users_table(conn) -> None:
        """Create users table."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                fullname TEXT,
                phone TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    @staticmethod
    async def _create_catalog_table(conn) -> None:
        """Create catalog table."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                id SERIAL PRIMARY KEY,
                title TEXT,
                description TEXT,
                file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    @staticmethod
    async def _create_works_table(conn) -> None:
        """Create works table."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id SERIAL PRIMARY KEY,
                file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    @staticmethod
    async def _create_reviews_table(conn) -> None:
        """Create reviews table."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                text TEXT,
                file_id TEXT,
                media_type TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    @staticmethod
    async def _create_orders_table(conn) -> None:
        """Create orders table."""
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

    # ======================= USERS QUERIES =======================

    async def add_user(
        self,
        telegram_id: int,
        fullname: str,
        phone: str = None,
        username: str = None
    ) -> None:
        """
        Add a new user or update existing if already exists.

        Args:
            telegram_id: User's Telegram ID
            fullname: User's full name
            phone: User's phone number (optional)
            username: User's Telegram username (optional)
        """
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
            """, telegram_id, fullname, phone, username)

    async def get_users(self) -> list:
        """
        Get all users.

        Returns:
            List of user records
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM users
                ORDER BY created_at DESC
            """)

    # ======================= ORDERS QUERIES =======================

    async def add_order(self, telegram_id: int, data: dict) -> None:
        """
        Create a new order.

        Args:
            telegram_id: User's Telegram ID
            data: Dictionary with order data
        """
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
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
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

    async def get_orders(self) -> list:
        """
        Get all orders.

        Returns:
            List of order records
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM orders
                ORDER BY created_at DESC
            """)

    async def count_orders_by_date(self, date_str: str) -> int:
        """
        Count orders for a specific date.

        Args:
            date_str: Date string in format DD.MM.YYYY

        Returns:
            Number of orders on that date
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*)
                FROM orders
                WHERE date_delivery = $1
            """, date_str)

    # ======================= CATALOG QUERIES =======================

    async def get_catalog(self) -> list:
        """
        Get all catalog items.

        Returns:
            List of catalog records
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM catalog
                ORDER BY created_at DESC
            """)

    # ======================= WORKS QUERIES =======================

    async def get_works(self) -> list:
        """
        Get all works.

        Returns:
            List of works records
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM works
                ORDER BY created_at DESC
            """)

    # ======================= REVIEWS QUERIES =======================

    async def get_reviews(self) -> list:
        """
        Get all reviews.

        Returns:
            List of review records
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT *
                FROM reviews
                ORDER BY created_at DESC
            """)
