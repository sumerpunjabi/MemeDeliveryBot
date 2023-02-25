import praw
import psycopg2
import os


def reddit_connect():
    try:

        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        user_agent = os.getenv("USER_AGENT")
        username = os.getenv("USERNAME")
        password = os.getenv("password")

        # creates reddit object to access subreddit
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password)

        sub = reddit.subreddit('memes')

        # return subreddit to main to fetch image
        return sub

    except OSError or AttributeError or TypeError as Error:

        print('Reddit Connection Error')
        print(Error)


def db_connect():
    try:
        db_key = os.getenv("db_key")

        conn = psycopg2.connect(
            db_key,
            sslmode='require')
        return conn

    except OSError or AttributeError or TypeError as Error:

        print('Database connection Error')
        print(Error)
