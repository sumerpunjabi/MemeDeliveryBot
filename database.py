from get_connection import db_connect


def insert_into_db(subreddit, post_id, title, upvote, ratio):

    insert = "INSERT INTO post (sub_name, id, title, upvote, upvote_ratio) " \
             "VALUES (%s, %s, %s, %s ,%s)"
    values = (subreddit, post_id, title, upvote, ratio)

    try:
        bot_db = db_connect()

        with bot_db.cursor() as cursor:
            cursor.execute(insert, values)
        bot_db.commit()
        bot_db.close()

        print('Database Insertion Complete')

    except OSError or AttributeError or TypeError as Error:
        print(Error)
        print('Database Insertion Error')

