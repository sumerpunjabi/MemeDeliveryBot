from get_image import select_image
from get_connections import reddit_connect
from database import insert_into_db
from publish import post


def main():
    """
    Main function to fetch an image from Reddit, post it, and store the post details in a database.
    """
    # starts connection to reddit to fetch image
    subreddit = reddit_connect()

    # selects post from sub and passes it to download
    selected_post = select_image(subreddit)

    # post the selected image
    post(selected_post.url, selected_post.title)

    # insert post details into db
    insert_into_db(selected_post.id, selected_post.title, selected_post.url)


if __name__ == "__main__":
    main()
