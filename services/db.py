# db.py
import psycopg2
from flask import abort
import os



DATABASE_URL  = os.environ.get('DATABASE_URL')

def get_db():
    """Return a new database connection."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as ex:
        print(f"❌ DB Connection Failed: {ex}")
        abort(500)

def init_db():
    """Initialize DB table and sequence."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    category TEXT,
                    sub_category TEXT,
                    description TEXT,
                    amount REAL,
                    date_time TEXT
                )
        """)
        conn.commit()

        # Sync sequence
        cur.execute("""
            SELECT setval(
                pg_get_serial_sequence('transactions', 'id'),
                COALESCE((SELECT MAX(id) FROM transactions), 0) + 1,
                true
            )
        """)
        conn.commit()

        # Add users table to the database
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.commit()

        # Add user_id column to transactions table
        cur.execute("""
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)
        """)
        conn.commit()

        # Add passwords table to the database
        cur.execute("""
            CREATE TABLE IF NOT EXISTS passwords (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id)
            )
        """)
        conn.commit()

        cur.close()
        conn.close()
        print("✅ DB initialized and sequence synced")
    except Exception as ex:
        print(f"❌ DB Initialization failed: {ex}")
        abort(500)
