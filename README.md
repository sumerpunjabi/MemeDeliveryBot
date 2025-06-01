# Instagram Content Creator Bot

This project helps automate content creation and posting to Instagram using content sourced from Reddit. It has two main functionalities:
1.  Fetching and posting images from specified subreddits.
2.  Generating video reels from Reddit posts (including title, selftext, and top comments) with text-to-speech and background media, and then uploading them to Instagram.

## Features

### Image Posting
- Fetches top images from a specified subreddit.
- Posts images to Instagram with a caption.
- Stores posted content details in a database.

### Reel Creation & Upload
- Fetches content (title, selftext, top comments) from a Reddit post URL.
- Converts text segments to speech using Text-to-Speech (TTS) engines.
- Generates images with text overlays for each segment.
- Supports custom background video and audio for reels.
- Assembles video segments, TTS audio, and background media using `ffmpeg`.
- Provides a command-line interface (`reel_command.py`) to generate and upload reels.
- Allows optional sharing of the reel to the Instagram feed.

## Setup

### 1. Dependencies
- Install Python 3.x.
- Install `ffmpeg` and ensure it's in your system's PATH. `ffmpeg` is required for video processing in the reel creation part.
- Install Python packages:
  ```bash
  pip install -r requirements.txt
  ```
  **Note:** The `requirements.txt` file might have a UTF-16 encoding. If you encounter issues, you might need to convert it to UTF-8 first or install packages manually by inspecting the file content. Common packages include `praw`, `requests`, `psycopg2`, `Pillow`, `moviepy` (or direct `ffmpeg` calls are used), `gTTS` or other TTS libraries.

### 2. Configuration

**A. For Image Posting (`main.py`):**
- **Instagram Credentials:** Configure your Instagram Account ID, Access Token, and API endpoint base in `defines.py` within the `get_credentials()` function.
- **Reddit API Credentials (for image fetching):** Credentials for `praw` should be set up as per `praw` documentation (e.g., via a `praw.ini` file or environment variables) if `reddit_connect()` in `get_connections.py` requires them.
- **Database:** The `database.py` script uses `psycopg2` for PostgreSQL. Ensure you have a PostgreSQL database running and configure the connection details (host, database name, user, password) within `database.py`. Run the table creation script if needed: `python scripts/create_table.py`.

**B. For Reel Creation (`reel_command.py` & `reel_creator/`):**
- **Reddit API Credentials:** Add your Reddit client ID, client secret, user agent (and optionally username/password for script authentication) in `reel_creator/reel_config.py`.
- **Instagram API Credentials (for reel uploading):** Configure your Instagram User ID and Access Token in `reel_creator/reel_config.py` for the `upload_reel` functionality.
- **TTS Engine:** The default TTS is gTTS. You can configure voice parameters in `reel_creator/reel_config.py`. If using other TTS engines, additional setup might be needed.
- **Fonts:** Ensure the font paths in `reel_creator/reel_config.py` (e.g., `IM_FONT_REGULAR_PATH`, `IM_FONT_BOLD_PATH`) point to valid `.ttf` font files. Default fonts are included in `reel_creator/assets/fonts/`.
- **Temporary Directories:** The system will create temporary directories under `reel_creator/assets/temp/` for processing. Ensure write permissions.

## Usage

### 1. Posting Images
To fetch an image from Reddit and post it to Instagram:
```bash
python main.py
```
Ensure `defines.py` and `database.py` are correctly configured.

### 2. Generating and Uploading Reels
Use the `reel_command.py` script:
```bash
python reel_command.py --url <REDDIT_POST_URL> [options]
```
**Key Options:**
-   `--url` / `-u` (required): URL of the Reddit post.
-   `--output_path` / `-o`: Full path to save the generated MP4 reel (e.g., `my_reels/my_video.mp4`). Defaults to `./reels_output/<reddit_post_id_or_generic_name>.mp4`.
-   `--caption` / `-c`: Caption for the Instagram Reel. Defaults to the Reddit post title.
-   `--no_upload` / `-n`: Generate video only, do not upload to Instagram.
-   `--share_to_feed`: Set to "true" or "false" to share/not share the reel to your main Instagram feed. Defaults to "true".

Example:
```bash
python reel_command.py -u "https://www.reddit.com/r/somecoolsubreddit/comments/xyz123/a_great_story/" -o "my_reels/story_reel.mp4" -c "Check out this story!"
```

You can also test the core reel generation logic by running `reel_creator/main.py` directly, which has a test setup in its `if __name__ == "__main__":` block.

## File Structure (Simplified)

```
.
├── main.py                 # Main script for Reddit image posting
├── publish.py              # Handles Instagram publishing for images
├── database.py             # Database interaction (PostgreSQL)
├── get_connections.py      # Reddit connection for image posting
├── defines.py              # Credentials and constants for image posting
├── reel_command.py         # CLI for generating and uploading reels
├── requirements.txt        # Project dependencies
├── reel_creator/           # Package for reel creation logic
│   ├── main.py             # Core reel generation orchestration
│   ├── reel_config.py      # Configuration for reel creator
│   ├── reel_tts.py         # Text-to-Speech handling
│   ├── imagenarator.py     # Image generation from text
│   ├── reel_assembler.py   # Video assembly using ffmpeg
│   ├── instagram_uploader.py # Handles reel uploading to Instagram
│   ├── assets/             # Assets for reel creation (fonts, temp files)
│   └── ...                 # Other helper modules
├── scripts/                # Utility scripts (e.g., DB setup)
└── README.md               # This file
```

## Contributing

Contributions are welcome! Please follow these steps:
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Open a Pull Request.

## License

Consider adding an open-source license. The [MIT License](https://opensource.org/licenses/MIT) is a popular choice. Create a `LICENSE` file in the root of the project with the license text.
