import os
import psycopg2

conn = None
try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
    cur = conn.cursor()
    cur.execute("DELETE FROM post")
    conn.commit()
    print("All rows deleted successfully")
except psycopg2.Error as e:
    print(f'Database operation Error: {e}')
finally:
    if conn is not None:
        conn.close()