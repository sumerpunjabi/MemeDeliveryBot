import os
import praw # For Reddit interaction
from typing import List, Tuple, Dict
import subprocess # For ffmpeg command

# Import modules from the reel_creator package
# Specific config values will be imported directly in functions where needed.
from . import reel_config
from . import reel_tts
from . import imagenarator
from . import reel_backgrounds
from . import reel_assembler
from . import cleanup
# from .fonts import get_font_path # This might be handled by imagenarator internally or via config paths

# --- Helper Functions ---

def fetch_reddit_content(reddit_url: str, reddit_config: dict) -> Tuple[str, str, List[str]]:
    """
    Fetches content from a Reddit URL using credentials from provided config.
    """
    print(f"Fetching Reddit content from: {reddit_url}")

    client_id = reddit_config.get("REDDIT_CLIENT_ID")
    client_secret = reddit_config.get("REDDIT_CLIENT_SECRET")
    user_agent = reddit_config.get("REDDIT_USER_AGENT")
    username = reddit_config.get("REDDIT_USERNAME") # Optional
    password = reddit_config.get("REDDIT_PASSWORD") # Optional

    if not client_id or "YOUR_REDDIT_CLIENT_ID" in client_id or \
       not client_secret or "YOUR_REDDIT_CLIENT_SECRET" in client_secret or \
       not user_agent or "YOUR_BOT_USER_AGENT" in user_agent:
        print("ERROR: Reddit API credentials (CLIENT_ID, CLIENT_SECRET, USER_AGENT) are not properly configured in reel_config.py.")
        print("Please update these placeholder values to fetch content from Reddit.")
        # Return empty content or raise an error, depending on desired handling
        # For now, returning empty to allow CLI to message and exit.
        # In a stricter environment, you might raise a ConfigurationError.
        raise ValueError("Reddit API credentials are not configured.")


    try:
        praw_kwargs = {
            "client_id": client_id,
            "client_secret": client_secret,
            "user_agent": user_agent,
        }
        if username and password: # Add username/password if provided for user context
            praw_kwargs["username"] = username
            praw_kwargs["password"] = password
            print("Attempting to authenticate with Reddit using username and password.")
        else:
            print("Attempting to authenticate with Reddit using client_id and client_secret (script auth).")

        reddit = praw.Reddit(**praw_kwargs)
        # Test authentication if possible (e.g., by trying to access PRAW's user object if in user context)
        if username:
            print(f"Authenticated as Reddit user: {reddit.user.me()}")
        else: # For script auth, just check if readonly is False (it should be for script apps)
             print(f"Reddit PRAW instance initialized. Read-only: {reddit.read_only}")


        submission = reddit.submission(url=reddit_url)
        submission.comment_sort = "top" # Sort comments by top

        title = submission.title
        post_body = submission.selftext

        comments_text = []
        # Fetch a few top comments (e.g., up to 5)
        # More complex logic might be needed for selecting "good" comments
        for i, comment in enumerate(submission.comments):
            if i >= 5: # Limit number of comments
                break
            if isinstance(comment, praw.models.MoreComments): # Skip "load more comments" objects
                continue
            comments_text.append(f"Comment {i+1}: {comment.body}")

        print(f"Successfully fetched: Title - '{title[:50]}...', Body - '{post_body[:50]}...', {len(comments_text)} comments.")
        return title, post_body, comments_text

    except Exception as e:
        print(f"Error fetching Reddit content: {e}")
        print("Using placeholder content due to error.")
        return ("Error Title", f"Could not fetch content from Reddit: {e}", [])


def split_text_into_segments(text: str, max_words: int) -> List[str]:
    """
    Splits a long text into smaller segments based on max_words.
    Tries to split at sentence endings if possible.
    """
    if not text: return []
    words = text.split()
    segments = []
    current_segment_words = []

    for word in words:
        current_segment_words.append(word)
        if len(current_segment_words) >= max_words:
            # Try to find a sentence end nearby for a cleaner cut
            segment_text = " ".join(current_segment_words)
            last_period = segment_text.rfind(". ")
            last_q_mark = segment_text.rfind("? ")
            last_ex_mark = segment_text.rfind("! ")

            split_pos = max(last_period, last_q_mark, last_ex_mark)

            if split_pos > 0 and len(segment_text) - (split_pos + 1) < max_words / 2: # Ensure reasonable split
                # Split after the punctuation
                segments.append(segment_text[:split_pos+1].strip())
                current_segment_words = segment_text[split_pos+2:].split()
            else:
                # Force split at max_words
                segments.append(" ".join(current_segment_words))
                current_segment_words = []

    if current_segment_words: # Add any remaining words
        segments.append(" ".join(current_segment_words))

    return [s for s in segments if s] # Filter out empty segments


# --- Main Orchestration Function ---

def generate_reel(
    reddit_url: str,
    output_directory: str, # Where the final reel video will be saved
    reel_id: str = None, # Unique ID for this reel, for temp folders. Auto-generate if None.
    background_video_url: str = None, # Optional: URL for background video
    background_audio_url: str = None, # Optional: URL for background audio
    background_video_path: str = None, # Optional: local path for background video
    background_audio_path: str = None  # Optional: local path for background audio
) -> str:
    """
    Generates a social media reel from a Reddit URL.

    Args:
        reddit_url (str): The URL of the Reddit post.
        output_directory (str): Directory to save the final reel.
        reel_id (str, optional): A unique ID for the reel. Auto-generated if None.
        background_video_url (str, optional): URL for background video.
        background_audio_url (str, optional): URL for background audio.
        background_video_path (str, optional): Local path for background video.
        background_audio_path (str, optional): Local path for background audio.

    Returns:
        str: Path to the generated reel video, or None if failed.
    """
    if not reel_id:
        import uuid
        reel_id = str(uuid.uuid4())[:8] # Short unique ID

    print(f"--- Starting Reel Generation for ID: {reel_id} ---")
    print(f"Output directory: {output_directory}")

    # Load necessary settings from reel_config
    # This makes it explicit which parts of config are being used by this core function
    cfg = reel_config

    # Ensure output directory exists
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        print(f"Created output directory: {output_directory}")

    # Temporary directory for this reel's assets
    current_reel_temp_dir = os.path.join(cfg.TEMP_DIR_BASE, reel_id)
    if not os.path.exists(current_reel_temp_dir):
        os.makedirs(current_reel_temp_dir)
        print(f"Created temp directory for reel: {current_reel_temp_dir}")

    image_paths: List[str] = []
    audio_segments_info: List[Dict] = [] # Store {'path': str, 'duration': float}

    try:
        # 1. Fetch Reddit Content
        reddit_api_cfg = {
            "REDDIT_CLIENT_ID": cfg.REDDIT_CLIENT_ID,
            "REDDIT_CLIENT_SECRET": cfg.REDDIT_CLIENT_SECRET,
            "REDDIT_USER_AGENT": cfg.REDDIT_USER_AGENT,
            "REDDIT_USERNAME": cfg.REDDIT_USERNAME,
            "REDDIT_PASSWORD": cfg.REDDIT_PASSWORD,
        }
        title, post_body, comments = fetch_reddit_content(reddit_url, reddit_api_cfg)

        if not title and not post_body and not comments: # fetch_reddit_content might raise error first
             raise ValueError("No content fetched from Reddit.")

        # --- Title Segment ---
        if title:
            tts_params_title = {**cfg.TTS_VOICE_PARAMS} # Start with general params
            # Add any title-specific TTS overrides if needed, e.g. different speed/voice

            title_audio_path, title_audio_duration = reel_tts.save_text_to_mp3(
                reel_id=reel_id,
                text=title,
                filename="title_audio.mp3",
                output_dir=os.path.join(current_reel_temp_dir, "mp3"), # Explicit output dir
                tts_provider=cfg.TTS_PROVIDER,
                language=cfg.TTS_LANGUAGE,
                # Pass relevant specific params from TTS_VOICE_PARAMS
                slow=tts_params_title.get('gTTS_slow', False),
                tld=tts_params_title.get('gTTS_tld', 'com') if cfg.TTS_PROVIDER == "gTTS" else None,
                # other provider params can be added here
            )
            audio_segments_info.append({'path': title_audio_path, 'duration': title_audio_duration})

            # Image for title - imagenarator now reads from config directly
            # We might pass overrides if needed: font_path=cfg.IM_FONT_BOLD_PATH, font_size=cfg.IM_TITLE_FONT_SIZE
            title_image_path = imagenarator.imagemaker(
                text=title,
                id="img_title",
                folder_name=os.path.join(reel_id, "img"), # Path relative to assets/
                # Specific overrides if imagemaker takes them, else it uses config
                # font_path=cfg.IM_FONT_BOLD_PATH,
                # font_size=cfg.IM_TITLE_FONT_SIZE
            )
            image_paths.append(title_image_path)
        else:
            title_audio_duration = 0.0

        # --- Body Segment(s) ---
        if post_body:
            body_segments = split_text_into_segments(post_body, cfg.MAX_WORDS_PER_IMAGE_SEGMENT)
            for i, segment_text in enumerate(body_segments):
                segment_audio_path, segment_audio_duration = reel_tts.save_text_to_mp3(
                    reel_id=reel_id,
                    text=segment_text,
                    filename=f"body_audio_{i}.mp3",
                    output_dir=os.path.join(current_reel_temp_dir, "mp3"),
                    tts_provider=cfg.TTS_PROVIDER,
                    language=cfg.TTS_LANGUAGE,
                    slow=cfg.TTS_VOICE_PARAMS.get('gTTS_slow', False),
                    tld=cfg.TTS_VOICE_PARAMS.get('gTTS_tld', 'com') if cfg.TTS_PROVIDER == "gTTS" else None,
                )
                audio_segments_info.append({'path': segment_audio_path, 'duration': segment_audio_duration})

                img_path = imagenarator.imagemaker(
                    text=segment_text,
                    id=f"img_body_{i}",
                    folder_name=os.path.join(reel_id, "img")
                    # font_path=cfg.IM_FONT_REGULAR_PATH, # Example if passed
                    # font_size=cfg.IM_FONT_SIZE
                )
                image_paths.append(img_path)

        # --- Comment Segments ---
        for i, comment_text in enumerate(comments[:3]): # Max 3 comments for now
            segment_audio_path, segment_audio_duration = reel_tts.save_text_to_mp3(
                reel_id=reel_id,
                text=comment_text,
                filename=f"comment_audio_{i}.mp3",
                output_dir=os.path.join(current_reel_temp_dir, "mp3"),
                tts_provider=cfg.TTS_PROVIDER,
                language=cfg.TTS_LANGUAGE,
                slow=cfg.TTS_VOICE_PARAMS.get('gTTS_slow', False),
                tld=cfg.TTS_VOICE_PARAMS.get('gTTS_tld', 'com') if cfg.TTS_PROVIDER == "gTTS" else None,
            )
            audio_segments_info.append({'path': segment_audio_path, 'duration': segment_audio_duration})

            img_path = imagenarator.imagemaker(
                text=comment_text,
                id=f"img_comment_{i}",
                folder_name=os.path.join(reel_id, "img")
            )
            image_paths.append(img_path)

        if not image_paths or not audio_segments_info:
            raise ValueError("No text content processed into images or audio.")

        total_speech_duration = sum(item['duration'] for item in audio_segments_info)
        image_durations = [item['duration'] for item in audio_segments_info]
        # Ensure total_speech_duration is not zero if there are segments.
        # This can happen if TTS fails to return valid durations.
        if not total_speech_duration and audio_segments_info:
            print("Warning: Total speech duration is zero. TTS might have failed to get durations. Using default image durations.")
            # Fallback: assign a default duration (e.g. 3s) for each image if TTS duration failed
            default_duration_per_image = 3.0
            image_durations = [default_duration_per_image] * len(image_paths)
            total_speech_duration = sum(image_durations)
            if not total_speech_duration: # Still zero, means no images/audio
                 raise ValueError("Cannot proceed with zero total duration and no audio/image segments.")


        print(f"Total speech duration: {total_speech_duration:.2f}s from {len(audio_segments_info)} segments.")
        print(f"Image paths: {image_paths}")
        print(f"Image durations: {image_durations}")

        # 3. Prepare Background Media
        # Priority: Function args > reel_config user-set > reel_config defaults
        bg_vid_path_final = background_video_path if background_video_path is not None else cfg.BG_VIDEO_PATH_OR_URL
        bg_aud_path_final = background_audio_path if background_audio_path is not None else cfg.BG_AUDIO_PATH_OR_URL
        # URLs from function args are handled by checking if path_final is a URL

        chopped_bg_video, chopped_bg_audio = reel_backgrounds.chop_background(
            reel_id=reel_id,
            # Pass resolved paths/URLs. chop_background will determine if it's URL or local.
            video_url=bg_vid_path_final if isinstance(bg_vid_path_final, str) and bg_vid_path_final.startswith(('http://', 'https://')) else None,
            video_file_path=bg_vid_path_final if isinstance(bg_vid_path_final, str) and not bg_vid_path_final.startswith(('http://', 'https://')) else None,
            audio_url=bg_aud_path_final if isinstance(bg_aud_path_final, str) and bg_aud_path_final.startswith(('http://', 'https://')) else None,
            audio_file_path=bg_aud_path_final if isinstance(bg_aud_path_final, str) and not bg_aud_path_final.startswith(('http://', 'https://')) else None,
            duration=total_speech_duration,
            # chop_background can also read from reel_config for its defaults if specific paths are None
        )
        if not chopped_bg_video and cfg.BG_USE_VIDEO:
            raise ValueError("Failed to prepare background video, but BG_USE_VIDEO is True.")
        if not chopped_bg_audio and cfg.BG_USE_AUDIO:
            print("Warning: Failed to prepare background audio, or none was specified/found.")
            # Continue without separate background audio, video's own audio might be used or silent.

        # 4. Assemble the Reel
        final_reel_filename = f"{cfg.OUTPUT_FILENAME_PREFIX}_{reel_id}.{cfg.DEFAULT_OUTPUT_FORMAT}"

        concatenated_speech_path = os.path.join(current_reel_temp_dir, "mp3", "full_speech.mp3")
        if len(audio_segments_info) > 1:
            print("Concatenating audio segments...")
            input_files_for_ffmpeg = [seg['path'] for seg in audio_segments_info]
            concat_list_path = os.path.join(current_reel_temp_dir, "mp3", "ffmpeg_audio_list.txt")
            with open(concat_list_path, "w") as f:
                for audio_file_path_seg in input_files_for_ffmpeg:
                    f.write(f"file '{os.path.abspath(audio_file_path_seg)}'\n")
            try:
                ffmpeg_cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list_path,
                    '-c', 'copy', concatenated_speech_path
                ]
                process = subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
                print(f"Concatenated speech audio saved to: {concatenated_speech_path}")
                main_audio_for_assembly = concatenated_speech_path
            except subprocess.CalledProcessError as e:
                print(f"Error concatenating audio with ffmpeg: {e.stderr}")
                raise ValueError("Failed to concatenate speech audio.") from e
            except FileNotFoundError:
                print("ERROR: ffmpeg command not found. Cannot concatenate audio.")
                main_audio_for_assembly = audio_segments_info[0]['path']
        elif audio_segments_info:
            main_audio_for_assembly = audio_segments_info[0]['path']
        else: # Should have been caught earlier by check for image_paths/audio_segments_info
            raise ValueError("No audio segments to assemble.")

        # reel_assembler will use width/height/fps from config internally now
        final_video_path = reel_assembler.assemble_reel(
            reel_id=reel_id,
            audio_path=main_audio_for_assembly,
            image_paths=image_paths,
            image_durations=image_durations,
            background_video_path=chopped_bg_video, # This is the processed (e.g. cropped, looped) background
            # background_audio_path=chopped_bg_audio, # assemble_reel may mix this or use main_audio_for_assembly's audio
            output_filename=final_reel_filename, # Saved in assets/temp/{reel_id}/ initially
            # background_is_9_16 is now read from config by reel_assembler's prepare_background
            # W, H, FPS are also read from config by assemble_reel
        )

        # Move final video to the specified output_directory
        # The final_video_path from assemble_reel is like "assets/temp/reel_id/reel_reel_id.mp4"
        final_output_destination = os.path.join(output_directory, os.path.basename(final_video_path))
        os.rename(final_video_path, final_output_destination) # move, not copy
        print(f"Final reel saved to: {final_output_destination}")

        return final_output_destination # Return the actual final path

    except ValueError as ve: # Catch config or content errors
        print(f"!!! Reel Generation Failed for ID {reel_id} due to ValueError: {ve} !!!")
        import traceback
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"!!! Reel Generation Failed for ID {reel_id} due to an unexpected error: {e} !!!")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 5. Cleanup
        PERFORM_CLEANUP = False # User can set this via config or a CLI flag in future
        if PERFORM_CLEANUP:
            print(f"Cleaning up temporary files for reel ID: {reel_id}")
            cleanup.cleanup_temp_files(reel_id=reel_id, temp_base_dir=cfg.TEMP_DIR_BASE)
        else:
            print(f"Skipping cleanup for reel ID: {reel_id}. Temp files in: {current_reel_temp_dir}")
        print(f"--- Reel Generation Finished for ID: {reel_id} ---")


if __name__ == "__main__":
    print("--- Running Main Reel Generation Test ---")

    # For direct execution, ensure reel_config is loaded and paths are valid
    cfg = reel_config

    # Ensure necessary base directories from config exist
    if not os.path.exists(cfg.ASSETS_DIR): os.makedirs(cfg.ASSETS_DIR)
    if not os.path.exists(cfg.FONTS_DIR): os.makedirs(cfg.FONTS_DIR) # Should contain dummy fonts by now
    if not os.path.exists(cfg.TEMP_DIR_BASE): os.makedirs(cfg.TEMP_DIR_BASE)
    # BACKGROUND_MEDIA_DIR might not be in reel_config explicitly, but assets/backgrounds
    # For the test, we use a local dummy background, so ensure assets/backgrounds exists
    dummy_bg_dir = os.path.join(cfg.ASSETS_DIR, "backgrounds")
    if not os.path.exists(dummy_bg_dir): os.makedirs(dummy_bg_dir)


    # Check if default font paths in config are valid after they were created
    if not os.path.exists(cfg.IM_FONT_REGULAR_PATH):
        print(f"ERROR: Default regular font not found at {cfg.IM_FONT_REGULAR_PATH}")
        print("The test might fail if imagemaker cannot find this font.")
    if not os.path.exists(cfg.IM_FONT_BOLD_PATH):
        print(f"ERROR: Default bold font not found at {cfg.IM_FONT_BOLD_PATH}")

    # Example Reddit URL (replace with a valid one for a real test)
    example_url = "https://www.reddit.com/r/shortstories/comments/120g17h/wp_the_moment_the_aliens_arrived_humanity_was/"
    # A simpler one for quicker tests if the above is too long:
    # example_url = "https://www.reddit.com/r/Showerthoughts/comments/10z0k5j/maybe_plants_are_farming_us_giving_us_oxygen/"

    # Output directory for the generated reel (e.g., a 'generated_reels' folder in project root)
    # PROJECT_ROOT in config points to parent of reel_creator package dir.
    reel_output_dir = os.path.join(cfg.PROJECT_ROOT, "generated_reels_output")
    if not os.path.exists(reel_output_dir):
        os.makedirs(reel_output_dir)

    print(f"Test Reel ID: main_test_001")
    print(f"Using Reddit URL: {example_url}")
    print(f"Output will be saved in: {reel_output_dir}")

    # Set to True to run the full generation.
    # Requires:
    # 1. ffmpeg installed and in PATH.
    # 2. Reddit API credentials in reel_config.py NOT be placeholders.
    # 3. Internet connection.
    RUN_FULL_GENERATION_TEST = False # Set to True to run the actual generation attempt
    print(f"RUN_FULL_GENERATION_TEST is set to {RUN_FULL_GENERATION_TEST}")
    if "YOUR_REDDIT_CLIENT_ID" in cfg.REDDIT_CLIENT_ID:
        print("WARNING: Reddit API credentials in reel_config.py are placeholders. Full test will likely fail to fetch content.")
        RUN_FULL_GENERATION_TEST = False # Force disable if creds are placeholders

    if RUN_FULL_GENERATION_TEST:
        # Create a dummy 16:9 background video for testing if not using a URL
        # This will be placed in "reel_creator/assets/backgrounds/dummy_test_bg.mp4"
        dummy_bg_video_path = os.path.join(dummy_bg_dir, "dummy_test_bg.mp4")

        if not os.path.exists(dummy_bg_video_path):
            print(f"Creating dummy background video at {dummy_bg_video_path}...")
            try:
                # Using ffmpeg directly via subprocess, as the ffmpeg-python lib might not be available
                # in the global scope when just running a file.
                ffmpeg_exe = "ffmpeg" # Assumes ffmpeg is in PATH
                cmd = [
                    ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", dummy_bg_video_path
                ]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"Dummy 16:9 background video created at {dummy_bg_video_path}")
            except Exception as e:
                print(f"Error creating dummy 16:9 background: {e}")
                print("Please ensure ffmpeg is installed and in PATH.")
                dummy_bg_video_path = None # Cannot proceed with this background if creation fails

        # Override config's default background to use this local dummy one for the test
        # This ensures the test doesn't rely on external URLs if not desired.
        custom_bg_video_path = dummy_bg_video_path if dummy_bg_video_path and os.path.exists(dummy_bg_video_path) else None
        custom_bg_audio_path = None # Let it use video's audio or be silent for this test

        generated_reel_path = generate_reel(
            reddit_url=example_url,
            output_directory=reel_output_dir,
            reel_id="main_test_config_001",
            background_video_path=custom_bg_video_path,
            background_audio_path=custom_bg_audio_path
        )

        if generated_reel_path:
            print(f"\nSUCCESS: Reel generation test completed. Video at: {generated_reel_path}")
        else:
            print("\nFAILURE: Reel generation test failed.")
    else:
        print("\nSkipping full reel generation test based on RUN_FULL_GENERATION_TEST flag or placeholder Reddit credentials.")

    print("--- End of Main Reel Generation Test ---")
