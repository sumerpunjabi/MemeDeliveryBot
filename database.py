from get_connections import db_connect
from psycopg2 import Error
from typing import Tuple

def insert_into_db(post_id: str, title: str, url: str) -> None:
    """
    Inserts a post into the database.

    Args:
        post_id: ID of the post
        title: Title of the post
        url: URL of the post
    """
    insert_query = "INSERT INTO post (id, title, url) VALUES (%s, %s, %s)"
    values = (post_id, title, url)

    try:
        with db_connect() as db:
            with db.cursor() as cursor:
                cursor.execute(insert_query, values)
            db.commit()
            print('Database Insertion Complete')

    except Error as e:
        print(f'Database Insertion Error: {e}')