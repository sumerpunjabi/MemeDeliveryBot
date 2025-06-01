import argparse
import os
import sys

# Assuming reel_creator package is in PYTHONPATH or installed
# Add project root to sys.path for direct execution if reel_creator is not installed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from reel_creator.main import generate_reel
    from reel_creator.instagram_uploader import upload_reel, ConfigurationError as UploaderConfigurationError, APIError as UploaderAPIError
    # Import reel_config and scanner functions
    from reel_creator import reel_config
    from reel_creator.reddit_scanner import fetch_top_posts_from_subreddits, select_best_post, add_processed_reel_id
except ImportError as e:
    print(f"Error importing from reel_creator: {e}")
    print("Please ensure reel_creator is installed or PYTHONPATH is set correctly.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

DEFAULT_OUTPUT_DIR = "reels_output"

def extract_reddit_post_id(url: str) -> str:
    """
    Extracts a potential Reddit post ID from the URL for default naming.
    This is a simplistic approach.
    """
    try:
        parts = url.rstrip("/").split("/")
        # A typical post URL structure is /r/subreddit/comments/post_id/title/
        if "comments" in parts and len(parts) > parts.index("comments") + 1:
            return parts[parts.index("comments") + 1]
    except Exception:
        pass # Ignore errors, will fallback to generic name
    return None

def handle_reel_command(args):
    """
    Handles the logic for the instagram_reel command.
    """
    print("INFO: --- Instagram Reel Generation and Upload Process Starting ---")

    reddit_url_to_process = args.url
    operation_mode = "user-provided URL mode" if reddit_url_to_process else "automatic post selection mode"
    print(f"INFO: Operating in {operation_mode}.")

    selected_submission_id = None # To store ID if auto-selected
    selected_submission_title = None # To store title if auto-selected

    if reddit_url_to_process is None:
        print("INFO: No specific Reddit URL provided. Attempting to automatically select a post...")
        try:
            print(f"INFO: Fetching top posts from default subreddits: {reel_config.DEFAULT_REEL_SUBREDDITS}")
            submissions = fetch_top_posts_from_subreddits(reel_config.DEFAULT_REEL_SUBREDDITS)

            if not submissions: # Check if fetch_top_posts_from_subreddits returned empty
                print("ERROR: Failed to fetch any posts from Reddit (fetch_top_posts_from_subreddits returned empty). Cannot select a post.")
                print("INFO: Please check Reddit API credentials in reel_config.py and scanner logs for more details.")
                return

            selected_submission = select_best_post(submissions)
            if selected_submission:
                reddit_url_to_process = selected_submission.url
                selected_submission_id = selected_submission.id
                selected_submission_title = selected_submission.title
                # The add_processed_reel_id is now called by select_best_post if a post is chosen,
                # but we should call it here to confirm this specific selection is final for this run.
                # However, select_best_post doesn't add, it just filters. So, adding here is correct.
                add_processed_reel_id(reel_config.PROCESSED_REEL_POSTS_FILE, selected_submission_id)
                print(f"INFO: Automatically selected post: '{selected_submission_title}'")
                print(f"INFO: URL: {reddit_url_to_process}")
                print(f"INFO: Post ID {selected_submission_id} has been recorded as processed for this run.")
            else:
                print("ERROR: Failed to automatically select a suitable Reddit post (select_best_post returned None).")
                print("INFO: This could be due to all fetched posts being unsuitable (e.g., stickied, NSFW, already processed, or other filters). Check scanner logs.")
                return
        except Exception as e: # Catch any unexpected error from scanner functions
            print(f"ERROR: An unexpected error occurred during automatic post selection: {e}")
            import traceback
            traceback.print_exc()
            return
    else:
        print(f"INFO: Using user-provided Reddit URL: {reddit_url_to_process}")
        # Future enhancement: fetch submission for user-provided URL to get canonical ID and add to processed list.

    if not reddit_url_to_process: # Final check if a URL was determined
        print("CRITICAL ERROR: No Reddit URL to process. Exiting.")
        return

    print(f"INFO: Final Reddit URL for processing: {reddit_url_to_process}")

    # 1. Determine Output Path
    # Ensure output_dir is defined before it's potentially used by filename_base logic
    output_dir_base_name = os.path.dirname(args.output_path) if args.output_path else DEFAULT_OUTPUT_DIR
    if not os.path.exists(output_dir_base_name):
        try:
            os.makedirs(output_dir_base_name)
            print(f"INFO: Created output directory: {output_dir_base_name}")
        except OSError as e:
            print(f"ERROR: Could not create output directory {output_dir_base_name}: {e}")
            return

    post_id_for_naming = selected_submission_id if selected_submission_id else extract_reddit_post_id(reddit_url_to_process) # No "or """ needed due to check above

    if not args.output_path:
        filename_base = post_id_for_naming if post_id_for_naming else "generated_reel" # Ensure filename_base is always valid
        determined_output_path = os.path.join(output_dir_base_name, f"{filename_base}.mp4")
    else:
        determined_output_path = args.output_path

    output_dir_for_generate_reel = os.path.dirname(determined_output_path)

    print(f"INFO: Output video path set to: {determined_output_path}")

    # Determine actual_caption
    if args.caption:
        actual_caption = args.caption
        print(f"INFO: Using user-provided caption: \"{actual_caption}\"")
    elif selected_submission_title: # Use title from auto-selected post if caption not given
        actual_caption = selected_submission_title
        print(f"INFO: Using title from auto-selected post as caption: \"{actual_caption}\"")
    else: # Fallback to fetching title if URL was given but no caption, or use default
        if reddit_url_to_process: # Should always be true here due to earlier check
            print(f"INFO: Attempting to fetch title from Reddit URL for caption...")
            try:
                from reel_creator.main import fetch_reddit_content # fetch_reddit_content needs config dict
                reddit_api_cfg_for_caption = {
                    "REDDIT_CLIENT_ID": reel_config.REDDIT_CLIENT_ID,
                    "REDDIT_CLIENT_SECRET": reel_config.REDDIT_CLIENT_SECRET,
                    "REDDIT_USER_AGENT": reel_config.REDDIT_USER_AGENT,
                    "REDDIT_USERNAME": reel_config.REDDIT_USERNAME,
                    "REDDIT_PASSWORD": reel_config.REDDIT_PASSWORD,
                }
                title_for_caption, _, _ = fetch_reddit_content(reddit_url_to_process, reddit_api_cfg_for_caption)
                if title_for_caption:
                    actual_caption = title_for_caption
                    print(f"INFO: Using fetched title as caption: \"{actual_caption}\"")
                else:
                    actual_caption = "Reel created with ReelCreatorBot"
                    print(f"WARNING: Fetched title was empty. Using default caption: \"{actual_caption}\"")
            except Exception as e:
                print(f"WARNING: Could not auto-fetch title for caption from URL due to: {e}. Using default caption.")
                actual_caption = "Check out this cool reel!"
        else: # Should not be reached if reddit_url_to_process is guaranteed
             actual_caption = "Check out this cool reel!"
             print(f"INFO: Using generic default caption: \"{actual_caption}\"")

    video_file_path = None

    # 2. Call generate_reel
    try:
        print(f"INFO: Starting reel generation for URL: {reddit_url_to_process}...")

        reel_id_for_generation = selected_submission_id if selected_submission_id else extract_reddit_post_id(reddit_url_to_process) or "cli_reel"
        print(f"INFO: Using reel_id for generation: {reel_id_for_generation}")

        video_file_path = generate_reel(
            reddit_url=reddit_url_to_process,
            output_directory=output_dir_for_generate_reel,
            reel_id=reel_id_for_generation
        )

        if video_file_path and os.path.exists(video_file_path):
            print(f"INFO: Reel generated successfully: {video_file_path}")
        else:
            print("ERROR: Reel generation failed or video file not found at the expected path.")
            return # Exit if generation failed

    except Exception as e:
        print(f"ERROR: An error occurred during reel generation: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Call upload_reel (if not --no_upload)
    if not args.no_upload:
        if not video_file_path:
            print("ERROR: Cannot upload because video file path is not available from generation step.")
            return

        share_to_feed_bool = args.share_to_feed.lower() == "true"

        print(f"INFO: \nStarting Instagram upload for {video_file_path}...")
        print(f"INFO: Caption for upload: \"{actual_caption}\"")
        print(f"INFO: Share to feed setting: {share_to_feed_bool}")

        try:
            media_id = upload_reel(
                video_path=video_file_path,
                caption=actual_caption,
                share_to_feed=share_to_feed_bool
            )
            if media_id:
                print(f"SUCCESS: Reel uploaded successfully to Instagram! Media ID: {media_id}")
            else:
                print("ERROR: Instagram upload failed. Media ID not returned. Check logs from instagram_uploader for details.")
        except UploaderConfigurationError as e:
            print(f"ERROR: Instagram Upload Configuration Error: {e}")
            print("INFO: Please ensure your Instagram API credentials (access token, user ID) are correctly set in reel_config.py.")
        except UploaderAPIError as e:
            print(f"ERROR: Instagram API Error during upload: {e}")
        except FileNotFoundError: # Should be caught by generate_reel, but good practice
            print(f"ERROR: Video file not found for upload: {video_file_path}")
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during Instagram upload: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("INFO: Skipping Instagram upload as per --no_upload flag.")

    print("INFO: --- Process Complete ---")


def main():
    parser = argparse.ArgumentParser(
        description="Generate an Instagram Reel from a Reddit post and optionally upload it.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--url", "-u",
        type=str,
        required=False, # Changed to False
        default=None,   # Default to None
        help=("URL of the Reddit post. If not provided, a suitable post will be automatically "
              "selected from default subreddits (e.g., AskReddit, shortstories) "
              "based on top daily score and suitability filters.")
    )
    parser.add_argument(
        "--output_path", "-o",
        type=str,
        default=None, # Default will be constructed
        help="Full path to save the generated MP4 reel (e.g., my_reels/my_video.mp4). "
             f"Defaults to ./{DEFAULT_OUTPUT_DIR}/<reddit_post_id_or_generic_name>.mp4"
    )
    parser.add_argument(
        "--caption", "-c",
        type=str,
        default=None,
        help="Caption for the Instagram Reel. Defaults to the Reddit post title."
    )
    parser.add_argument(
        "--no_upload", "-n",
        action="store_true",
        help="Generate video only, do not upload to Instagram."
    )
    parser.add_argument(
        "--share_to_feed",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Share Reel to Instagram feed (true/false). Defaults to true."
    )
    parser.add_argument(
        "--config_file", # This argument is defined but not fully plumbed into reel_creator.main yet
        type=str,
        default=None,
        help="Path to a custom reel_creator TOML/Python config file (Feature not fully implemented in core library yet)."
    )

    args = parser.parse_args()

    if args.config_file:
        print(f"Note: Custom config file '{args.config_file}' provided, but this feature is not fully implemented in the core library yet.")
        # Here, you would typically load the config file and update reel_config settings.
        # For now, it's just an acknowledgement.

    handle_reel_command(args)

if __name__ == "__main__":
    main()
