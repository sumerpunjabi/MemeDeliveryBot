import os

# -----------------------------------------------------------------------------
# Reel Creator Configuration File
# -----------------------------------------------------------------------------
# This file contains all the settings for the Reel Creator bot.
# Ensure you fill in any placeholder values (like API keys) before running the bot.
# Paths are generally constructed relative to the project root or this file's location.

# --- Project Paths ---
# Absolute path to the directory containing the 'reel_creator' package
# (i.e., the parent directory of the directory this config file is in).
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REEL_CREATOR_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(REEL_CREATOR_DIR, "assets") # assets dir inside reel_creator
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
TEMP_DIR_BASE = os.path.join(ASSETS_DIR, "temp") # Base for temporary files per reel

# --- Instagram API Settings ---
# These values MUST be filled by the user after following the token generation process.
# See documentation in `instagram_uploader.py` for how to obtain these.
INSTAGRAM_API_SETTINGS = {
    "INSTAGRAM_ACCESS_TOKEN": "YOUR_ACCESS_TOKEN_HERE",  # Long-lived Instagram User Access Token
    "INSTAGRAM_USER_ID": "YOUR_INSTAGRAM_USER_ID_HERE",    # Your Instagram User ID (numeric string)
}

# --- Reddit API Credentials ---
# These are crucial for fetching content from Reddit.
# Register an app on Reddit (https://www.reddit.com/prefs/apps) to get these.
# Choose "script" type app. The redirect URI can be http://localhost:8080 (though not strictly used for script apps).
REDDIT_CLIENT_ID = "YOUR_REDDIT_CLIENT_ID"           # Found under your app on Reddit
REDDIT_CLIENT_SECRET = "YOUR_REDDIT_CLIENT_SECRET"     # Found under your app on Reddit
REDDIT_USER_AGENT = "YOUR_BOT_USER_AGENT/1.0 by u/YourUsername" # Custom User-Agent string (be descriptive)
# Optional: For user-context PRAW instance (e.g., to access user-specific subreddits or save posts)
# If not needed, leave blank. For most content fetching, script-app credentials (client_id/secret) are enough.
REDDIT_USERNAME = ""
REDDIT_PASSWORD = ""


# --- Video Settings ---
VIDEO_WIDTH = 1080      # Width of the output reel video in pixels (standard for 9:16)
VIDEO_HEIGHT = 1920     # Height of the output reel video in pixels (standard for 9:16)
VIDEO_FPS = 30          # Frames per second for the output video

# --- Imagemaker (Text-on-Screen) Settings ---
# These settings control the appearance of text rendered onto image slides.
# Ensure the font files exist at these paths.
IM_FONT_REGULAR_PATH = os.path.join(FONTS_DIR, "Roboto-Regular.ttf") # Path to regular font
IM_FONT_BOLD_PATH = os.path.join(FONTS_DIR, "Roboto-Bold.ttf")       # Path to bold font
IM_FONT_SIZE = 60               # Default font size for body text
IM_TITLE_FONT_SIZE = 70         # Font size for titles (if different)
IM_TEXT_COLOR = "#FFFFFF"       # Color of the text (hex code)
IM_BACKGROUND_COLOR = "rgba(20,20,20,0.7)" # Background for text slides (R,G,B,A for semi-transparency)
                                           # Use "none" or `None` for fully transparent if image is complex.
IM_TEXT_WRAP_WIDTH = 25         # Approximate number of characters to wrap text at

# --- TTS (Text-to-Speech) Settings ---
TTS_PROVIDER = "gTTS"           # Options: "gTTS" (Google Text-to-Speech), "pyttsx3" (offline, needs setup)
                                # Future: "elevenlabs" (requires API_KEY in TTS_VOICE_PARAMS)
TTS_LANGUAGE = "en"             # Language code for TTS (e.g., "en", "es", "fr")
TTS_OUTPUT_BITRATE = "192k"     # Bitrate for the output MP3 audio from TTS
# Placeholder for provider-specific voice parameters.
# For gTTS, `lang` and `tld` can be specified. `slow` is another gTTS param.
# For pyttsx3, might include voice ID, rate, volume.
# For ElevenLabs: `ELEVENLABS_API_KEY = "YOUR_KEY"`, `ELEVENLABS_VOICE_ID = "voice_id"`
TTS_VOICE_PARAMS = {
    "gTTS_tld": "com",          # Top-level domain for gTTS (e.g., "com", "co.uk" for different accents)
    "gTTS_slow": False,         # Whether gTTS should speak slowly
    # "pyttsx3_rate": 150,      # Example for pyttsx3 if used
    # "pyttsx3_voice_index": 0, # Example for pyttsx3
}

# --- Background Media Settings ---
# Settings for the background video and audio of the reel.
BG_USE_VIDEO = True             # Set to False to have a static image or solid color background (not fully implemented yet)
BG_VIDEO_PATH_OR_URL = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4" # Default background video
                                # Can be a local file path or a direct URL.
                                # If using local files, consider placing them in `reel_creator/assets/backgrounds`
BG_IS_ALREADY_9_16 = False      # If the background video is already 9:16, set True to skip cropping.

BG_USE_AUDIO = True             # Whether to use separate background audio. If False, uses audio from BG_VIDEO or TTS only.
BG_AUDIO_PATH_OR_URL = "http://commondatastorage.googleapis.com/codeskulptor-assets/sounddogs/soundtrack.mp3" # Default background audio
                                # Can be local or URL.
BG_AUDIO_VOLUME = 0.10          # Volume for the background audio (0.0 to 1.0). 0.10 means 10% volume.

# --- Reel Assembly Configuration ---
TITLE_IMAGE_DURATION_SECONDS = 3.0 # How long the title image (if any) stays on screen
MAX_WORDS_PER_IMAGE_SEGMENT = 15 # For splitting long text into multiple images
OUTPUT_FILENAME_PREFIX = "reel"
DEFAULT_OUTPUT_FORMAT = "mp4"

# --- FFmpeg / MoviePy Configuration ---
FFMPEG_PRESET = "medium" # Affects encoding speed vs. file size/quality (e.g., "ultrafast", "medium", "slow")
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
NUM_THREADS = os.cpu_count() or 2 # Number of threads for video processing, defaults to CPU count or 2

# --- Content Filtering ---
ALLOW_NSFW_CONTENT = False # Filter out NSFW posts if set to False
PROCESSED_REEL_POSTS_FILE = os.path.join(ASSETS_DIR, "processed_reel_posts.txt") # File to track processed post IDs
DEFAULT_REEL_SUBREDDITS = ["shortstories", "Showerthoughts", "LifeProTips", "explainlikeimfive", "todayilearned", "AmItheAsshole"] # Default subreddits for auto-selection


# --- Function to print config for verification ---
def print_config_summary():
    """Prints a summary of the current configuration settings."""
    print("--- Reel Creator Configuration Summary ---")
    settings_to_print = {
        "Project Root": PROJECT_ROOT,
        "Assets Dir": ASSETS_DIR,
        "Temp Dir Base": TEMP_DIR_BASE,
        "Instagram User ID": INSTAGRAM_API_SETTINGS.get("INSTAGRAM_USER_ID"),
        "Reddit Client ID": REDDIT_CLIENT_ID,
        "Video Dimensions": f"{VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS}fps",
        "Imagemaker Font (Regular)": IM_FONT_REGULAR_PATH,
        "TTS Provider": TTS_PROVIDER,
        "Background Video Default": BG_VIDEO_PATH_OR_URL,
        "Background Audio Default": BG_AUDIO_PATH_OR_URL,
        "Background Audio Volume": BG_AUDIO_VOLUME,
        "Allow NSFW Content": ALLOW_NSFW_CONTENT,
        "Processed Posts File": PROCESSED_REEL_POSTS_FILE,
        "Default Reel Subreddits": DEFAULT_REEL_SUBREDDITS,
    }
    for key, value in settings_to_print.items():
        print(f"{key}: {value}")

    if "YOUR_ACCESS_TOKEN_HERE" in INSTAGRAM_API_SETTINGS.get("INSTAGRAM_ACCESS_TOKEN", ""):
        print("WARNING: Instagram Access Token is a placeholder.")
    if "YOUR_REDDIT_CLIENT_ID" in REDDIT_CLIENT_ID:
        print("WARNING: Reddit Client ID is a placeholder.")

    # Ensure ASSETS_DIR exists as PROCESSED_REEL_POSTS_FILE depends on it
    if not os.path.exists(ASSETS_DIR):
        print(f"WARNING: ASSETS_DIR ('{ASSETS_DIR}') does not exist. It may be created if needed by the application.")
        # os.makedirs(ASSETS_DIR, exist_ok=True) # Could auto-create, or let app logic handle it.

    print("-----------------------------------------")

if __name__ == "__main__":
    print_config_summary()
    # Verify font paths
    print(f"\nVerifying font path (Regular): {IM_FONT_REGULAR_PATH} - Exists: {os.path.exists(IM_FONT_REGULAR_PATH)}")
    print(f"Verifying font path (Bold): {IM_FONT_BOLD_PATH} - Exists: {os.path.exists(IM_FONT_BOLD_PATH)}")
    print(f"Processed posts file path: {PROCESSED_REEL_POSTS_FILE}")


    if not os.path.exists(IM_FONT_REGULAR_PATH) or not os.path.exists(IM_FONT_BOLD_PATH):
        print("\nWARNING: One or more default font files are missing at the specified paths.")
        print(f"Please ensure '{os.path.basename(IM_FONT_REGULAR_PATH)}' and '{os.path.basename(IM_FONT_BOLD_PATH)}' exist in '{FONTS_DIR}'.")
        print("You can download Roboto fonts from Google Fonts: https://fonts.google.com/specimen/Roboto")

    print("\nTo use the bot, ensure all 'YOUR_...' placeholders are filled, especially for API keys.")
    print("Paths are resolved based on this file's location or project structure.")
