import os
import json
import random
import subprocess
import ffmpeg
import yt_dlp # youtube-dl is now yt-dlp
# from . import reel_config # Placeholder for future config import

# Define possible locations for background assets.
# This might be configurable via reel_config.py in the future.
DEFAULT_BACKGROUND_VIDEO_JSON = os.path.join(os.path.dirname(__file__), "utils", "background_videos.json")
DEFAULT_BACKGROUND_AUDIO_JSON = os.path.join(os.path.dirname(__file__), "utils", "background_audios.json")
DOWNLOAD_PATH = "assets/backgrounds" # Could be in reel_config

def get_video_duration(video_path: str) -> float:
    """Gets the duration of a video file using ffprobe."""
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
        return float(video_info["duration"])
    except Exception as e:
        print(f"Error getting duration for {video_path}: {e}")
        return 0.0

def download_video(video_url: str, output_path: str, video_id: str) -> str:
    """
    Downloads a video from a URL using yt-dlp.
    Saves it to output_path/video_id.mp4
    Returns the full path to the downloaded video.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    full_video_path = os.path.join(output_path, f"{video_id}.mp4")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", # Standard format selection
        "outtmpl": full_video_path,
        "noplaylist": True,
        "quiet": True,
        "merge_output_format": "mp4", # Ensure output is mp4 if separate streams are downloaded
    }

    # Avoid re-downloading if file exists and is non-empty
    if os.path.exists(full_video_path) and os.path.getsize(full_video_path) > 0:
        print(f"Video {video_id} already downloaded: {full_video_path}")
        return full_video_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"Video downloaded successfully: {full_video_path}")
        return full_video_path
    except Exception as e:
        print(f"Error downloading video {video_url}: {e}")
        return None


def chop_background(
    reel_id: str,
    video_url: str = None,
    audio_url: str = None,
    video_file_path: str = None, # Allow using a local file
    audio_file_path: str = None, # Allow using a local file
    duration: float = 60.0, # Desired duration of the chopped segment
    background_video_json_path: str = None,
    background_audio_json_path: str = None
) -> tuple[str, str]:
    """
    Downloads (if URL provided) and chops a random segment from a background video and audio.
    If local file paths are provided, uses them directly.
    Saves chopped segments to assets/temp/{reel_id}/background/.
    Returns paths to the chopped video and audio.
    """
    output_video_path = f"assets/temp/{reel_id}/background/video.mp4"
    output_audio_path = f"assets/temp/{reel_id}/background/audio.mp3"

    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)

    # Video processing
    actual_video_file_path = None
    if video_file_path and os.path.exists(video_file_path):
        actual_video_file_path = video_file_path
        print(f"Using local background video: {actual_video_file_path}")
    elif video_url:
        print(f"Attempting to download background video from URL: {video_url}")
        # For simplicity, using a fixed ID for downloaded background for now
        # In a real scenario, this might be derived from the URL or be a hash
        actual_video_file_path = download_video(video_url, os.path.join(DOWNLOAD_PATH, "videos"), "downloaded_bg_video")
    else:
        # Fallback to JSON list if no direct video_url or file_path given
        video_json = background_video_json_path or DEFAULT_BACKGROUND_VIDEO_JSON
        if not os.path.exists(video_json):
            raise FileNotFoundError(f"Background video JSON not found at {video_json} and no video URL/path provided.")
        with open(video_json, "r") as f:
            bck_vids = json.load(f)
        chosen_video_info = random.choice(bck_vids)
        video_name = chosen_video_info["name"]
        video_url_from_json = chosen_video_info["url"]
        print(f"Chosen background video from JSON: {video_name}")
        actual_video_file_path = download_video(video_url_from_json, os.path.join(DOWNLOAD_PATH, "videos"), video_name)

    if not actual_video_file_path or not os.path.exists(actual_video_file_path):
        raise FileNotFoundError(f"Failed to obtain background video. Path: {actual_video_file_path}")

    video_duration = get_video_duration(actual_video_file_path)
    if video_duration <= 0:
        raise ValueError(f"Could not determine duration or duration is zero for video: {actual_video_file_path}")

    start_time_video = 0
    if video_duration > duration:
        start_time_video = random.uniform(0, video_duration - duration)

    try:
        (
            ffmpeg.input(actual_video_file_path, ss=start_time_video, t=duration)
            .output(output_video_path, vcodec="libx264", acodec="aac", preset="medium", strict="-2") # Ensure audio is encoded for temp file
            .run(overwrite_output=True, quiet=True)
        )
        print(f"Background video chopped and saved to: {output_video_path}")
    except ffmpeg.Error as e:
        print(f"ffmpeg error chopping video: {e.stderr.decode('utf8') if e.stderr else str(e)}")
        raise

    # Audio processing (similar logic, simplified for now)
    actual_audio_file_path = None
    if audio_file_path and os.path.exists(audio_file_path):
        actual_audio_file_path = audio_file_path
        print(f"Using local background audio: {actual_audio_file_path}")
    elif audio_url:
        print(f"Attempting to download background audio from URL: {audio_url}")
        actual_audio_file_path = download_video(audio_url, os.path.join(DOWNLOAD_PATH, "audios"), "downloaded_bg_audio") # Using download_video for audio too
    else:
        audio_json = background_audio_json_path or DEFAULT_BACKGROUND_AUDIO_JSON
        if os.path.exists(audio_json): # Audio is optional if not provided by other means
            with open(audio_json, "r") as f:
                bck_audios = json.load(f)
            chosen_audio_info = random.choice(bck_audios)
            audio_name = chosen_audio_info["name"]
            audio_url_from_json = chosen_audio_info["url"]
            print(f"Chosen background audio from JSON: {audio_name}")
            actual_audio_file_path = download_video(audio_url_from_json, os.path.join(DOWNLOAD_PATH, "audios"), audio_name)
        else:
            print("No background audio URL, path, or JSON specified. Background video's audio will be used if present, or silent if not.")


    if actual_audio_file_path and os.path.exists(actual_audio_file_path):
        # This part assumes the downloaded 'video' (which is an audio file) can be processed by ffmpeg for its audio stream
        audio_duration_probe = get_video_duration(actual_audio_file_path) # Probe for 'video' duration, which is audio length
        if audio_duration_probe <= 0:
             print(f"Warning: Could not determine duration for audio file: {actual_audio_file_path}. Using as is.")
             start_time_audio = 0
             desired_audio_duration = duration # try to match video duration
        else:
            start_time_audio = 0
            if audio_duration_probe > duration:
                start_time_audio = random.uniform(0, audio_duration_probe - duration)
            desired_audio_duration = duration

        try:
            (
                ffmpeg.input(actual_audio_file_path, ss=start_time_audio, t=desired_audio_duration)
                .output(output_audio_path, acodec="mp3", ab="192k") # Standard MP3 output
                .run(overwrite_output=True, quiet=True)
            )
            print(f"Background audio chopped and saved to: {output_audio_path}")
        except ffmpeg.Error as e:
            print(f"ffmpeg error chopping audio: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            # Fallback: if chopping fails, try to copy the whole file if it's short enough, or just don't provide audio
            if audio_duration_probe <= duration * 1.1: # If it's roughly the right length
                 subprocess.run(["cp", actual_audio_file_path, output_audio_path], check=True)
                 print(f"Used full audio file as fallback: {output_audio_path}")
            else:
                output_audio_path = None # Indicate no audio processed
                print("Failed to process background audio, proceeding without it.")
    else:
        # If no external audio, the video's own audio (if any) will be used by reel_assembler
        # or it will be silent. For now, explicitly set to None if not processed here.
        print("No separate background audio source provided or processed.")
        output_audio_path = None

    return output_video_path, output_audio_path


if __name__ == "__main__":
    test_reel_id = "bg_chop_test_01"
    temp_dir = f"assets/temp/{test_reel_id}/background"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # To fully test, you'd need sample video/audio files or accessible URLs.
    # And dummy JSON files if not providing URLs/paths directly.

    # Create dummy background_videos.json and background_audios.json in a temporary utils folder
    mock_utils_path = os.path.join(os.path.dirname(__file__), "utils")
    os.makedirs(mock_utils_path, exist_ok=True)

    dummy_video_json_path = os.path.join(mock_utils_path, "background_videos.json")
    dummy_audio_json_path = os.path.join(mock_utils_path, "background_audios.json")

    # Dummy video URL (replace with a real, short, public domain video for actual testing)
    # Using a common test video source like BBB is too large for typical CI/testing.
    # For now, the code will try to use this, likely fail if not available, then error.
    # A better test would mock yt-dlp or have a tiny local file.
    sample_video_url = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4" # A short test video
    sample_audio_url = "http://commondatastorage.googleapis.com/codeskulptor-assets/sounddogs/soundtrack.mp3" # Sample audio

    with open(dummy_video_json_path, "w") as f:
        json.dump([{"name": "sample_vid", "url": sample_video_url}], f)
    with open(dummy_audio_json_path, "w") as f:
        json.dump([{"name": "sample_aud", "url": sample_audio_url}], f)

    print("--- Test 1: Using URLs from JSON (requires internet & yt-dlp) ---")
    try:
        # This test requires yt-dlp to be installed and functional, and internet access.
        # It will download small files.
        chopped_v, chopped_a = chop_background(
            reel_id=test_reel_id,
            duration=5.0, # Chop 5 seconds
            background_video_json_path=dummy_video_json_path,
            background_audio_json_path=dummy_audio_json_path
        )
        print(f"Test 1 Result: Video - {chopped_v}, Audio - {chopped_a}")
        if chopped_v and os.path.exists(chopped_v): print(f"Video file {chopped_v} created.")
        else: print(f"Video file {chopped_v} NOT created or path is None.")
        if chopped_a and os.path.exists(chopped_a): print(f"Audio file {chopped_a} created.")
        else: print(f"Audio file {chopped_a} NOT created or path is None (may be intended if audio processing failed).")

    except Exception as e:
        print(f"Error in Test 1 (JSON URLs): {e}")
        print("This test might fail if yt-dlp is not installed or if there are network issues.")

    print("\n--- Test 2: Using direct video URL, no separate audio URL (requires internet & yt-dlp) ---")
    # This will use the audio from the video file itself.
    test_reel_id_2 = "bg_chop_test_02"
    try:
        chopped_v2, chopped_a2 = chop_background(
            reel_id=test_reel_id_2,
            video_url=sample_video_url, # Provide a direct video URL
            duration=4.0
        )
        print(f"Test 2 Result: Video - {chopped_v2}, Audio - {chopped_a2}")
        if chopped_v2 and os.path.exists(chopped_v2): print(f"Video file {chopped_v2} created.")
        else: print(f"Video file {chopped_v2} NOT created or path is None.")
        # chopped_a2 is expected to be None in this case, as no separate audio_url was given
        if chopped_a2 is None: print("Audio path is None as expected (using video's own audio).")
        elif os.path.exists(chopped_a2): print(f"Audio file {chopped_a2} created (unexpected).")
        else: print(f"Audio file {chopped_a2} path returned but file not found (unexpected).")


    except Exception as e:
        print(f"Error in Test 2 (Direct Video URL): {e}")

    # Cleanup (optional, comment out to inspect files)
    print("\nNote: Test files are in assets/temp/. Manual cleanup might be needed or enable below.")
    # import shutil
    # for item in [f"assets/temp/{test_reel_id}", f"assets/temp/{test_reel_id_2}", "assets/backgrounds", mock_utils_path]:
    #     if os.path.exists(item):
    #         shutil.rmtree(item)
    #         print(f"Cleaned up: {item}")
    if os.path.exists(dummy_video_json_path): os.remove(dummy_video_json_path)
    if os.path.exists(dummy_audio_json_path): os.remove(dummy_audio_json_path)
    if os.path.exists(mock_utils_path) and not os.listdir(mock_utils_path): os.rmdir(mock_utils_path)

    print("--- End of reel_backgrounds.py tests ---")
