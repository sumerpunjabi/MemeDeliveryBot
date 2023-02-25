from get_connection import db_connect

sql = 'SELECT id FROM post'
id_holder = []


def select_image(sub):

    try:
        bot_db = db_connect()

        with bot_db.cursor() as cursor:
            cursor.execute(sql)
            # makes a list of ids to check for repetition (not efficient)
            for row in cursor.fetchall():
                id_holder.append(row[0])

        bot_db.close()

        for submission in sub.top('day', limit=25):
            # checks for pinned and repeated posts

            flag = select_image_helper(submission)
            if flag:
                return submission

    except OSError or AttributeError or TypeError as Error:

        print('Failed to choose post')
        print(Error)


def select_image_helper(submission):
    if not submission.stickied and submission.id not in id_holder \
            and submission.url[-3:] != 'gif':
        # makes sure post is an image
        if 'post_hint' in vars(submission) and \
                vars(submission)['post_hint'] == 'image' and \
                submission.url[-3:] != 'gif':
            return True
    return False
