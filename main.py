from get_image import select_image
from get_connection import reddit_connect
from database import insert_into_db
from publish_content import post


def main():
    try:
        # starts connection to reddit to fetch image
        sub = reddit_connect()

        # selects post from sub and passes it to download
        selected_post = select_image(sub)

        post(selected_post.url, selected_post.title)

        # insert post details into db
        insert_into_db(sub.display_name, selected_post.id, selected_post.title,
                       selected_post.score, selected_post.upvote_ratio)

    except OSError or AttributeError or TypeError as Error:
        print(Error)
