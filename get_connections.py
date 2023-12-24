import os
import praw
import psycopg2

def reddit_connect():
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD")
        )

        sub = reddit.subreddit('memes')
        print("Connected to Reddit API")
        return sub
    except praw.exceptions.PRAWException as e:
        print(f'Reddit Connection Error: {e}')

def db_connect():
    conn = None
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
        return conn
    except psycopg2.Error as e:
        print(f'Database connection Error: {e}')
