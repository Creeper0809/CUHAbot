"""
Add attribute field to skill and monster tables
"""
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def add_attribute_columns():
    """Add attribute columns to skill and monster tables"""
    # Database connection parameters
    host = os.getenv("DATABASE_URL")
    port = int(os.getenv("DATABASE_PORT", 5432))
    user = os.getenv("DATABASE_USER")
    password = os.getenv("DATABASE_PASSWORD")
    database = os.getenv("DATABASE_TABLE")

    print(f"Connecting to {host}:{port}/{database}...")

    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )

    try:
        # Add attribute column to skill table
        print("Adding attribute column to skill table...")
        await conn.execute(
            "ALTER TABLE skill ADD COLUMN IF NOT EXISTS attribute VARCHAR(20) DEFAULT '무속성'"
        )
        print("✓ skill.attribute added")

        # Add attribute column to monster table
        print("Adding attribute column to monster table...")
        await conn.execute(
            "ALTER TABLE monster ADD COLUMN IF NOT EXISTS attribute VARCHAR(20) DEFAULT '무속성'"
        )
        print("✓ monster.attribute added")

        print("\n✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(add_attribute_columns())
