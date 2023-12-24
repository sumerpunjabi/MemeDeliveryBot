from get_connections import db_connect

def select_image(subreddit):
    """
    Selects an image from the subreddit that has not been posted before.
    """
    try:
        with db_connect() as db:
            id_set = get_posted_ids(db)
            for _ in range(100):
                for submission in subreddit.top('day', limit=100):
                    if is_new_image_post(submission, id_set):
                        print("Post Chosen")
                        return submission
                print("No new image post found, trying again...")
            raise Exception("Failed to find a new image post after 100 attempts")
    except Exception as e:
        print(f'Failed to choose post: {e}')


def get_posted_ids(db):
    """
    Fetches the ids of the posts that have already been posted.
    """
    id_set = set()
    with db.cursor() as cursor:
        cursor.execute('SELECT id FROM post')
        print("Connected to DB: checking old posts")
        for row in cursor.fetchall():
            id_set.add(row[0])
    return id_set


def is_new_image_post(submission, id_set):
    """
    Checks if a submission is a new image post.
    """
    is_image = 'post_hint' in vars(submission) and vars(submission)['post_hint'] == 'image'
    is_not_gif = submission.url[-3:] != 'gif'
    is_not_stickied = not submission.stickied
    is_not_posted = submission.id not in id_set

    return is_image and is_not_gif and is_not_stickied and is_not_posted
    