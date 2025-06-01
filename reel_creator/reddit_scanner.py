import praw
from prawcore.exceptions import PrawcoreException # For more specific PRAW errors
from typing import List, Dict, Set, Optional # Added Set and Optional
import os # Added os for path operations

# Attempt to import reel_config from the reel_creator package
try:
    from . import reel_config
except ImportError:
    # This fallback is for scenarios where the script might be run directly
    # and the package structure isn't immediately recognized.
    # It's less ideal than a proper package installation.
    import reel_config


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""
    pass


def fetch_top_posts_from_subreddits(subreddit_names: List[str], limit_per_subreddit: int = 25) -> List[praw.models.Submission]:
    """
    Fetches the top posts from a list of specified subreddits.

    Args:
        subreddit_names (List[str]): A list of subreddit names (e.g., ['memes', 'AskReddit']).
        limit_per_subreddit (int): The maximum number of top posts to fetch per subreddit.

    Returns:
        List[praw.models.Submission]: A list of PRAW Submission objects, or an empty list if
                                      Reddit API credentials are not configured or errors occur.
    """
    print("INFO: --- Reddit Post Scanner: Starting Fetch Top Posts ---")

    client_id = reel_config.REDDIT_CLIENT_ID
    client_secret = reel_config.REDDIT_CLIENT_SECRET
    user_agent = reel_config.REDDIT_USER_AGENT
    username = reel_config.REDDIT_USERNAME
    password = reel_config.REDDIT_PASSWORD

    if not client_id or "YOUR_REDDIT_CLIENT_ID" in client_id or \
       not client_secret or "YOUR_REDDIT_CLIENT_SECRET" in client_secret or \
       not user_agent or "YOUR_BOT_USER_AGENT" in user_agent:
        # This is a critical configuration error.
        error_msg = ("CRITICAL ERROR: Reddit API credentials (CLIENT_ID, CLIENT_SECRET, USER_AGENT) "
                     "are not properly configured in reel_config.py. Please update these placeholder values. "
                     "Cannot fetch posts from Reddit.")
        print(error_msg)
        # Consider raising ConfigurationError(error_msg) here if the calling code should handle it
        return []

    all_submissions: List[praw.models.Submission] = []
    print(f"INFO: Initializing PRAW Reddit instance with User Agent: {user_agent}")

    try:
        praw_kwargs = {
            "client_id": client_id,
            "client_secret": client_secret,
            "user_agent": user_agent,
        }
        if username and password and "YOUR_USERNAME" not in username and "YOUR_PASSWORD" not in password: # Ensure not placeholder
            praw_kwargs["username"] = username
            praw_kwargs["password"] = password
            print("INFO: Attempting to authenticate with Reddit using username and password.")
        else:
            print("INFO: Attempting to authenticate with Reddit using client_id and client_secret (script application auth).")

        reddit = praw.Reddit(**praw_kwargs)

        # Test authentication explicitly
        if username and password and "YOUR_USERNAME" not in username and "YOUR_PASSWORD" not in password:
            print(f"INFO: Successfully authenticated with Reddit as user: {reddit.user.me()}.")
        else:
            # For script auth, a common check is `reddit.user.me()` which would fail if not script app for userless.
            # A simpler check is just to see if read_only is False, but PRAW sets it based on actual auth.
            # If the previous calls didn't raise, PRAW considers itself initialized.
            print(f"INFO: Reddit PRAW instance initialized. Read-only status: {reddit.read_only}")
        print("INFO: PRAW Reddit instance initialization complete.")

    except PrawcoreException as e:
        print(f"ERROR: PRAW Core Exception during Reddit initialization: {e}. Check credentials and network.")
        return []
    except Exception as e: # Catch any other unexpected error during PRAW init
        print(f"ERROR: An unexpected error occurred during PRAW initialization: {e}")
        return []

    for sub_name in subreddit_names:
        print(f"\nINFO: Scanning subreddit: r/{sub_name}...")
        try:
            subreddit = reddit.subreddit(sub_name)
            # Accessing an attribute like display_name can trigger checks for subreddit existence/access
            print(f"INFO: Accessing r/{subreddit.display_name}...") # subreddit.display_name itself makes a call if not cached
            print(f"INFO: Fetching top {limit_per_subreddit} posts from r/{sub_name} for the 'day'...")

            current_subreddit_posts = []
            try:
                for post in subreddit.top('day', limit=limit_per_subreddit):
                    current_subreddit_posts.append(post)
            except Exception as e: # Catch broad errors during post iteration for this specific subreddit
                print(f"ERROR: Could not fetch all posts from r/{sub_name} due to: {e}. Processing what was fetched before error.")

            if current_subreddit_posts:
                print(f"INFO: Fetched {len(current_subreddit_posts)} posts from r/{sub_name}.")
                all_submissions.extend(current_subreddit_posts)
            else:
                print(f"INFO: No posts found or fetched from r/{sub_name} for the 'day' filter or limit was 0.")

        except praw.exceptions.Redirect: # Subreddit does not exist
            print(f"WARNING: Subreddit r/{sub_name} not found or has been redirected. Skipping.")
        except praw.exceptions.PRAWException as e: # More general PRAW exceptions
            print(f"WARNING: Could not process subreddit r/{sub_name} due to a PRAW API error: {e}. Skipping.")
        except PrawcoreException as e: # Lower-level PRAW core exceptions
            print(f"WARNING: Could not process subreddit r/{sub_name} due to a PRAW core error: {e}. Skipping.")
        except Exception as e: # Catch any other unexpected error for a specific subreddit
            print(f"WARNING: An unexpected error occurred while initializing or fetching from r/{sub_name}: {e}. Skipping.")

    total_fetched = len(all_submissions)
    print(f"\nINFO: --- Reddit Post Scanning Finished ---")
    print(f"INFO: Total posts fetched successfully across all subreddits: {total_fetched}")
    return all_submissions


# --- Helper functions for processed post tracking ---

def get_processed_reel_ids(file_path: str) -> Set[str]:
    """
    Reads a file containing one post ID per line and returns a set of these IDs.
    Handles FileNotFoundError by returning an empty set.
    """
    processed_ids: Set[str] = set()
    try:
        with open(file_path, 'r') as f:
            for line in f:
                processed_ids.add(line.strip())
        print(f"INFO: Loaded {len(processed_ids)} processed post IDs from '{file_path}'.")
    except FileNotFoundError:
        print(f"INFO: Processed posts file '{file_path}' not found. Assuming no posts processed yet.")
    except (IOError, OSError) as e:
        print(f"ERROR: Could not read processed posts file '{file_path}': {e}. Returning empty set.")
    return processed_ids

def add_processed_reel_id(file_path: str, post_id: str):
    """
    Appends a new post ID to the specified file, creating the directory if it doesn't exist.
    """
    try:
        # Ensure the directory for the file exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'a') as f:
            f.write(f"{post_id}\n")
        print(f"INFO: Added post ID '{post_id}' to processed list: {file_path}")
    except (IOError, OSError) as e:
        print(f"ERROR: Could not write post ID '{post_id}' to file '{file_path}': {e}")


# --- Function to select the best post ---

def select_best_post(submissions: List[praw.models.Submission]) -> Optional[praw.models.Submission]:
    """
    Selects the best post from a list of PRAW Submission objects based on suitability and upvotes.

    Args:
        submissions (List[praw.models.Submission]): A list of PRAW Submission objects.

    Returns:
        Optional[praw.models.Submission]: The selected Submission object, or None if no suitable post is found.
    """
    if not submissions:
        print("INFO: No submissions provided to select_best_post function.")
        return None

    initial_count = len(submissions)
    print(f"\nINFO: --- Selecting Best Post from {initial_count} Candidates ---")

    # Filter 1: Stickied posts
    suitable_posts = [s for s in submissions if not s.stickied]
    count_after_stickied_filter = len(suitable_posts)
    if initial_count != count_after_stickied_filter:
        print(f"INFO: Filtered out {initial_count - count_after_stickied_filter} stickied posts. Remaining: {count_after_stickied_filter}")

    # Filter 2: NSFW posts (if not allowed)
    if not reel_config.ALLOW_NSFW_CONTENT:
        non_nsfw_posts = [s for s in suitable_posts if not s.over_18]
        count_after_nsfw_filter = len(non_nsfw_posts)
        if count_after_stickied_filter != count_after_nsfw_filter:
            print(f"INFO: Filtered out {count_after_stickied_filter - count_after_nsfw_filter} NSFW posts. Remaining: {count_after_nsfw_filter}")
        suitable_posts = non_nsfw_posts
    else:
        print("INFO: NSFW content is allowed. Skipping NSFW filter.")

    # Filter 3: Already processed posts
    processed_post_ids = get_processed_reel_ids(reel_config.PROCESSED_REEL_POSTS_FILE)
    if processed_post_ids: # Only filter if there are processed IDs
        count_before_processed_filter = len(suitable_posts)
        newly_suitable_posts = [s for s in suitable_posts if s.id not in processed_post_ids]
        count_after_processed_filter = len(newly_suitable_posts)
        if count_before_processed_filter != count_after_processed_filter:
            print(f"INFO: Filtered out {count_before_processed_filter - count_after_processed_filter} already processed posts. Remaining: {count_after_processed_filter}")
        suitable_posts = newly_suitable_posts
    else:
        print("INFO: No processed post IDs found. Skipping processed filter.")

    if not suitable_posts:
        print("INFO: No suitable posts found after all filtering steps.")
        return None

    print(f"INFO: Selecting post with the highest score from {len(suitable_posts)} suitable candidates...")
    # Sort by score in descending order, then potentially by other factors if scores are tied (e.g., num_comments)
    # For now, max score is sufficient.
    best_post = max(suitable_posts, key=lambda post: post.score)

    print(f"INFO: Selected best post - ID: {best_post.id}, Score: {best_post.score}, Subreddit: r/{best_post.subreddit.display_name}, Title: '{best_post.title[:60]}...'")
    return best_post


if __name__ == '__main__':
    # This is a basic test block.
    # IMPORTANT: To run this test effectively, you MUST have valid Reddit API credentials
    # in your `reel_config.py` file. If they are placeholders, it will print an error and return [].

    print("--- Running Basic Test for reddit_scanner.py ---")

    # Check if config has placeholder values first
    is_config_placeholder = (
        not reel_config.REDDIT_CLIENT_ID or "YOUR_REDDIT_CLIENT_ID" in reel_config.REDDIT_CLIENT_ID or
        not reel_config.REDDIT_CLIENT_SECRET or "YOUR_REDDIT_CLIENT_SECRET" in reel_config.REDDIT_CLIENT_SECRET or
        not reel_config.REDDIT_USER_AGENT or "YOUR_BOT_USER_AGENT" in reel_config.REDDIT_USER_AGENT
    )

    if is_config_placeholder:
        print("\nWARNING: Reddit API credentials in reel_config.py are placeholders.")
        print("The test will likely not fetch any actual posts for `fetch_top_posts_from_subreddits`.")
        print("Please update reel_config.py with your credentials to test `fetch_top_posts_from_subreddits` fully.\n")
        # Even with placeholders, let it run to test the credential check logic.

    # Example: List of subreddits to scan
    # Using common, generally accessible subreddits for testing.
    # Replace with subreddits of interest if your credentials allow.
    example_subreddits = ["ShortStories", "Showerthoughts", "MadeMeSmile", "thissubredditdoesnotexistatall"] # Last one for error handling test

    print("\n--- Testing fetch_top_posts_from_subreddits ---")
    fetched_submissions = fetch_top_posts_from_subreddits(example_subreddits, limit_per_subreddit=2)

    if fetched_submissions:
        print(f"\nSuccessfully fetched {len(fetched_submissions)} submissions in total for testing `select_best_post`. Titles:")
        for i, submission in enumerate(fetched_submissions):
            try:
                # Basic check to ensure it's a Submission object with expected attributes
                print(f"  {i+1}. r/{submission.subreddit.display_name} - \"{submission.title[:60]}...\" (Score: {submission.score}, ID: {submission.id}, Stickied: {submission.stickied}, NSFW: {submission.over_18})")
            except Exception as e:
                print(f"Error accessing submission attributes: {e}")
    elif not is_config_placeholder: # If config was not placeholder but still got no results
        print("\nNo submissions fetched by `fetch_top_posts_from_subreddits`. This could be due to various reasons (see previous logs).")
    else: # Config was placeholder, and we correctly got an empty list or just the error message.
        print("\nAs expected with placeholder credentials, `fetch_top_posts_from_subreddits` did not actively fetch submissions beyond the credential check.")

    # --- Test select_best_post ---
    print("\n\n--- Testing select_best_post ---")

    # Ensure the processed posts file is clean for a predictable test, or use known state
    # For this test, let's ensure it's empty or doesn't exist to test adding to it.
    # A more robust test setup might involve creating a temporary processed_posts file.
    test_processed_file = reel_config.PROCESSED_REEL_POSTS_FILE
    if os.path.exists(test_processed_file):
        print(f"Temporarily backing up and clearing existing processed posts file: {test_processed_file}")
        # In a real test suite, you might copy it, clear it, then restore.
        # For now, let's just note its presence. A real test would manage this file.
        # For this flow, we'll just add to it if it exists.
        pass # Not clearing it automatically to avoid data loss if it's a real file.

    # Create some mock PRAW submission objects for more controlled testing of select_best_post
    # This is useful if actual fetching returns too few or unsuitable posts.
    class MockSubreddit:
        def __init__(self, name):
            self.display_name = name
    class MockSubmission:
        def __init__(self, id, title, score, stickied, over_18, subreddit_name="mocksubreddit"):
            self.id = id
            self.title = title
            self.score = score
            self.stickied = stickied
            self.over_18 = over_18
            self.subreddit = MockSubreddit(subreddit_name)
            # Add other attributes if your function uses them, e.g., self.url, self.selftext

    mock_submissions = [
        MockSubmission("mock001", "High Score, Suitable", 100, False, False),
        MockSubmission("mock002", "Stickied Post", 200, True, False),
        MockSubmission("mock003", "NSFW Post", 150, False, True),
        MockSubmission("mock004", "Already Processed (will add)", 120, False, False),
        MockSubmission("mock005", "Lower Score, Suitable", 80, False, False),
        MockSubmission("mock006", "Another High Score, Suitable", 100, False, False),
    ]

    # Add one to processed list for testing that filter
    if not is_config_placeholder: # Only if we might actually write to a real file
        add_processed_reel_id(test_processed_file, "mock004")


    # Combine fetched (if any) and mock submissions for a richer test set for select_best_post
    combined_test_submissions = fetched_submissions + mock_submissions
    if not combined_test_submissions:
        print("No submissions (neither fetched nor mocked) available to test `select_best_post`.")
    else:
        print(f"\nTesting `select_best_post` with {len(combined_test_submissions)} combined submissions.")

        # Test 1: Select with current ALLOW_NSFW_CONTENT setting
        print(f"Current reel_config.ALLOW_NSFW_CONTENT = {reel_config.ALLOW_NSFW_CONTENT}")
        best_post_selection = select_best_post(combined_test_submissions)

        if best_post_selection:
            print(f"\n`select_best_post` selected: ID {best_post_selection.id}, Title: '{best_post_selection.title}', Score: {best_post_selection.score}")
            assert not best_post_selection.stickied
            if not reel_config.ALLOW_NSFW_CONTENT:
                assert not best_post_selection.over_18
            # Add selected post to processed list for next potential run or test
            if not is_config_placeholder: # Only if we might actually write to a real file
                 add_processed_reel_id(test_processed_file, best_post_selection.id)
        else:
            print("\n`select_best_post` returned None (no suitable post found).")

        # Test 2: Temporarily allow NSFW and re-select (if NSFW was initially False)
        if not reel_config.ALLOW_NSFW_CONTENT:
            print("\nTesting `select_best_post` again, temporarily setting ALLOW_NSFW_CONTENT = True for this test run...")
            original_nsfw_setting = reel_config.ALLOW_NSFW_CONTENT
            reel_config.ALLOW_NSFW_CONTENT = True # Modify in-memory for this test

            best_post_nsfw_allowed = select_best_post(combined_test_submissions)
            if best_post_nsfw_allowed:
                print(f"\n`select_best_post` (NSFW allowed) selected: ID {best_post_nsfw_allowed.id}, Title: '{best_post_nsfw_allowed.title}', Score: {best_post_nsfw_allowed.score}, NSFW: {best_post_nsfw_allowed.over_18}")
                assert not best_post_nsfw_allowed.stickied # Still should not be stickied
                # If it selected the NSFW post, its score should be higher or it was the only one
                if best_post_nsfw_allowed.id == "mock003":
                    print("Correctly selected the NSFW post when allowed.")

            reel_config.ALLOW_NSFW_CONTENT = original_nsfw_setting # Reset to original
            print(f"Restored reel_config.ALLOW_NSFW_CONTENT to {original_nsfw_setting}")

    # Cleanup: remove the dummy processed ID if it was added to a real file and if it's a mock one.
    # This is tricky without a proper test framework's setup/teardown.
    # For now, if "mock004" was added, we can't easily remove just that line without reading/writing the whole file.
    # So, we'll skip auto-cleanup of the processed_posts.txt for this basic test.
    # Manual inspection/clearing of `reel_creator/assets/processed_reel_posts.txt` might be needed after tests.
    if os.path.exists(test_processed_file) and not is_config_placeholder:
        print(f"\nNote: '{test_processed_file}' may have been modified during the test.")
        print("Inspect or clear it if necessary, especially if mock IDs were added.")


    print("\n--- End of reddit_scanner.py Test ---")
