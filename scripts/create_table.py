import os
import psycopg2

conn = None
try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS post (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    """)
    conn.commit()
    print("Table created successfully")
except psycopg2.Error as e:
    print(f'Database connection Error: {e}')
finally:
    if conn is not None:
        conn.close()