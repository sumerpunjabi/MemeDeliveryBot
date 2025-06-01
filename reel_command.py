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
    from reel_creator import reel_config # To potentially access default paths or settings
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
    print("--- Instagram Reel Generation and Upload ---")

    # 1. Determine Output Path
    output_dir = os.path.dirname(args.output_path) if args.output_path else DEFAULT_OUTPUT_DIR
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except OSError as e:
            print(f"Error creating output directory {output_dir}: {e}")
            return

    # Try to get a somewhat unique filename if not provided
    filename_base = "generated_reel"
    if not args.output_path:
        post_id_for_name = extract_reddit_post_id(args.url)
        if post_id_for_name:
            filename_base = post_id_for_name
        determined_output_path = os.path.join(output_dir, f"{filename_base}.mp4")
    else:
        determined_output_path = args.output_path

    print(f"Output video path set to: {determined_output_path}")

    # Placeholder for actual post title - to be returned by generate_reel ideally
    actual_caption = args.caption
    video_file_path = None

    # 2. Call generate_reel
    try:
        print(f"\nStarting reel generation for URL: {args.url}...")
        # In the future, generate_reel could return (video_path, post_title)
        # For now, we assume it just returns video_path.
        # And caption is handled separately or needs to be fetched again if None.

        # If args.caption is None, we might need to fetch title here first, or rely on generate_reel to do it
        # and somehow pass it along. For this subtask, we'll use provided caption or a default.

        # generate_reel is expected to use its internal config for most things.
        # The `reel_id` could be derived from post_id_for_name for better temp folder naming.
        reel_id_for_generation = extract_reddit_post_id(args.url) or "cli_reel"

        video_file_path = generate_reel(
            reddit_url=args.url,
            output_directory=os.path.dirname(determined_output_path), # generate_reel saves it in output_directory/reel_id_prefix_reel_id.mp4
            reel_id=reel_id_for_generation
            # Note: generate_reel currently saves to assets/temp/{reel_id}/final_reel...
            # then moves to output_directory. We need to ensure filenames align or adjust.
            # For now, let's assume generate_reel saves it to the final intended path.
            # Re-evaluating generate_reel's signature:
            # `output_directory` is where the *final* reel is saved.
            # It constructs the final name itself. So we should pass `output_dir` not `determined_output_path`.
        )

        # If generate_reel uses its own naming convention within output_directory:
        # We need to know what that path is.
        # The current main.py's generate_reel saves "reel_output_dir/reel_id.mp4"
        # So, the `video_file_path` returned by it *is* the correct path.

        if video_file_path and os.path.exists(video_file_path):
            print(f"Reel generated successfully: {video_file_path}")
            # If caption is not provided, and generate_reel doesn't return it, we use a default.
            # This part needs refinement: ideally generate_reel returns title.
            if actual_caption is None:
                # Fetch title again (crude, should be returned by generate_reel)
                try:
                    from reel_creator.main import fetch_reddit_content
                    title, _, _ = fetch_reddit_content(args.url) # Only if API creds are set
                    actual_caption = title if title else "Reel created with ReelCreatorBot"
                except Exception as e:
                    print(f"Warning: Could not auto-fetch title for caption due to: {e}. Using default.")
                    actual_caption = "Check out this cool reel!"
                print(f"Using caption: \"{actual_caption}\"")

        else:
            print("Error: Reel generation failed or video file not found.")
            return # Exit if generation failed

    except Exception as e:
        print(f"An error occurred during reel generation: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Call upload_reel (if not --no_upload)
    if not args.no_upload:
        if not video_file_path:
            print("Cannot upload: Video file path is not available.")
            return

        share_to_feed_bool = args.share_to_feed.lower() == "true"

        print(f"\nStarting Instagram upload for {video_file_path}...")
        print(f"Caption: \"{actual_caption}\"")
        print(f"Share to feed: {share_to_feed_bool}")

        try:
            media_id = upload_reel(
                video_path=video_file_path,
                caption=actual_caption,
                share_to_feed=share_to_feed_bool
            )
            if media_id:
                print(f"Reel uploaded successfully to Instagram! Media ID: {media_id}")
            else:
                print("Error: Instagram upload failed. Check logs for details.")
        except UploaderConfigurationError as e:
            print(f"Instagram Upload Configuration Error: {e}")
            print("Please ensure your Instagram API credentials (access token, user ID) are correctly set in reel_config.py.")
        except UploaderAPIError as e:
            print(f"Instagram API Error: {e}")
        except FileNotFoundError as e: # Should be caught by generate_reel, but good practice
            print(f"Error: Video file not found for upload: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during Instagram upload: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\nSkipping Instagram upload as per --no_upload flag.")

    print("\n--- Process Complete ---")


def main():
    parser = argparse.ArgumentParser(
        description="Generate an Instagram Reel from a Reddit post and optionally upload it.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--url", "-u",
        type=str,
        required=True,
        help="URL of the Reddit post."
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
