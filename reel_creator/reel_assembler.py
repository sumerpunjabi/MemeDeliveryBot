import os
import random
import ffmpeg
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    CompositeAudioClip,
)
from moviepy.video.fx.all import crop # For potential background cropping
from . import reel_config as config # Import configuration

# W and H are now sourced from config within functions where needed.

def get_video_duration(video_path):
    """Gets the duration of a video file."""
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
        return float(video_info["duration"])
    except Exception as e:
        print(f"Error getting duration for {video_path}: {e}")
        return 0

def prepare_background(background_path: str, desired_duration: float, reel_id: str, is_already_9_16: bool = False):
    """
    Prepares background video by trimming or looping and ensuring 9:16 aspect ratio.
    Saves the processed background to a temporary path.
    Reads VIDEO_WIDTH, VIDEO_HEIGHT from config for aspect ratio calculations.
    Background output path now uses config.TEMP_DIR_BASE.
    """
    # Path for storing processed background, using base temp dir from config
    processed_bg_dir = os.path.join(config.TEMP_DIR_BASE, reel_id, "background")
    if not os.path.exists(processed_bg_dir):
        os.makedirs(processed_bg_dir)
    temp_bg_path = os.path.join(processed_bg_dir, "processed_background.mp4") # Standardized name

    video_duration = get_video_duration(background_path)
    if video_duration == 0:
        raise ValueError("Background video duration is zero or could not be determined.")

    # Trimming or looping logic (simplified from original)
    if video_duration > desired_duration:
        start_time = random.uniform(0, video_duration - desired_duration)
        (
            ffmpeg.input(background_path, ss=start_time, t=desired_duration)
            .output(temp_bg_path, c="copy") # Use copy if no filter applied, else re-encode
            .run(overwrite_output=True, quiet=True)
        )
    else: # Loop if shorter
        num_loops = int(desired_duration / video_duration) + 1
        # This creates a temporary file listing the input file multiple times for concat
        concat_file_path = f"assets/temp/{reel_id}/concat_list.txt"
        with open(concat_file_path, "w") as f:
            for _ in range(num_loops):
                f.write(f"file '{os.path.abspath(background_path)}'\n")
        (
            ffmpeg.input(concat_file_path, format='concat', safe=0)
            .output(temp_bg_path, c="copy", t=desired_duration)
            .run(overwrite_output=True, quiet=True)
        )
        os.remove(concat_file_path)

    # Aspect ratio adjustment
    if not is_already_9_16:
        # Load with moviepy for easier cropping if needed, then save
        clip = VideoFileClip(temp_bg_path)
        # Crop to 9:16, using dimensions from config
        video_w = config.VIDEO_WIDTH
        video_h = config.VIDEO_HEIGHT
        cropped_clip = crop(clip, width=int(clip.h * (video_w / video_h)), height=clip.h, x_center=clip.w / 2, y_center=clip.h / 2)

        # Save the cropped clip. Final scaling to target WxH is done in assemble_reel.
        # The output path for this intermediate cropped file:
        final_cropped_path = os.path.join(processed_bg_dir, "cropped_background.mp4")

        cropped_clip.write_videofile(
            final_cropped_path,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            threads=config.NUM_THREADS,
            preset=config.FFMPEG_PRESET,
            logger=None # Suppress moviepy console output
        )
        clip.close()
        cropped_clip.close()
        return final_cropped_path # Return path to this newly created cropped file

    # If already 9:16, the temp_bg_path (which contains the trimmed/looped original) is returned
    return temp_bg_path


def assemble_reel(
    reel_id: str,
    audio_path: str, # This is the main speech audio track
    image_paths: list[str],
    background_video_path: str, # This is the path to the *processed* background (trimmed, maybe cropped)
    output_filename: str, # Just the filename, e.g., "reel_final.mp4"
    image_durations: list[float] = None,
    # background_is_9_16 is now handled by prepare_background using config.BG_IS_ALREADY_9_16
    # W, H, FPS are now read from config
):
    """
    Assembles the final reel video using settings from reel_config.py.
    Images are assumed to be already at target resolution (e.g., 1080x1920 from imagemaker).
    """
    final_assembly_dir = os.path.join(config.TEMP_DIR_BASE, reel_id) # Base for this reel's temp files
    if not os.path.exists(final_assembly_dir):
        os.makedirs(final_assembly_dir) # Should already exist from main.py but ensure

    # Load dimensions and FPS from config
    video_w = config.VIDEO_WIDTH
    video_h = config.VIDEO_HEIGHT
    video_fps = config.VIDEO_FPS

    main_audio_clip = AudioFileClip(audio_path)
    total_audio_duration = main_audio_clip.duration

    # Prepare background
    # If background_is_9_16 is True, prepare_background will just trim/loop
    processed_background_path = prepare_background(background_video_path, total_audio_duration, reel_id, background_is_9_16)
    background_clip = VideoFileClip(processed_background_path).without_audio()


    # Create image clips
    # Assumes imagemaker produces full-frame 1080x1920 images.
    # These images will be overlaid directly.

    clips_to_overlay = []
    current_time = 0

    if image_durations and len(image_durations) == len(image_paths):
        # Use provided durations
        for i, img_path in enumerate(image_paths):
            duration = image_durations[i]
            img_clip = (
                ImageClip(img_path)
                .set_duration(duration)
                .set_start(current_time)
                .set_position(("center", "center")) # Center the 1080x1920 image
            )
            clips_to_overlay.append(img_clip)
            current_time += duration
    else:
        # Default: Divide audio duration equally among images (excluding title if handled separately)
        # For now, let's assume first image is title and gets a fixed duration, rest share the remainder
        if not image_paths:
            raise ValueError("No images provided for the reel.")

        title_duration = min(3, total_audio_duration) # Title image for 3 seconds or less if audio is short
        if len(image_paths) == 1:
            img_clip = (
                ImageClip(image_paths[0])
                .set_duration(total_audio_duration)
                .set_start(0)
                .set_position(("center", "center"))
            )
            clips_to_overlay.append(img_clip)
        else:
            # Title image
            img_clip_title = (
                ImageClip(image_paths[0])
                .set_duration(title_duration)
                .set_start(current_time)
                .set_position(("center", "center"))
            )
            clips_to_overlay.append(img_clip_title)
            current_time += title_duration

            # Remaining images share the rest of the duration
            remaining_duration = total_audio_duration - title_duration
            if remaining_duration > 0 and len(image_paths) > 1:
                duration_per_image = remaining_duration / (len(image_paths) - 1)
                for i, img_path in enumerate(image_paths[1:]):
                    img_clip = (
                        ImageClip(img_path)
                        .set_duration(duration_per_image)
                        .set_start(current_time)
                        .set_position(("center", "center"))
                    )
                    clips_to_overlay.append(img_clip)
                    current_time += duration_per_image

    # Ensure the background clip is scaled to the final target WxH for the composite
    background_clip_final = background_clip.resize(newsize=(video_w, video_h))

    # Create final video composition
    final_video = CompositeVideoClip(
        [background_clip_final] + clips_to_overlay,
        size=(video_w, video_h)
    )
    final_video = final_video.set_audio(main_audio_clip)
    final_video = final_video.set_duration(total_audio_duration)
    final_video = final_video.set_fps(video_fps)


    # Output path for the final assembled video (within the reel's temp directory)
    # Example: reel_creator/assets/temp/reel123/reel_final.mp4
    output_path_temp = os.path.join(final_assembly_dir, output_filename)

    final_video.write_videofile(
        output_path_temp,
        codec=config.VIDEO_CODEC,
        audio_codec=config.AUDIO_CODEC,
        threads=config.NUM_THREADS,
        preset=config.FFMPEG_PRESET,
        fps=video_fps, # Ensure FPS is set for write_videofile
        logger=None
    )

    # Close all clips
    main_audio_clip.close()
    background_clip.close()
    if background_clip_final is not background_clip: # if resize created a new clip instance
        background_clip_final.close()
    for clip in clips_to_overlay:
        clip.close()
    final_video.close()

    print(f"Reel assembled at: {output_path}")
    return output_path

if __name__ == "__main__":
    # Create dummy files for testing
    reel_id_test = "asm_test_01" # New ID for assembler test

    # Ensure base temp directory from config exists for the test setup
    if not os.path.exists(config.TEMP_DIR_BASE):
        os.makedirs(config.TEMP_DIR_BASE)

    # Specific temp directory for this test run, following structure used in functions
    # e.g. reel_creator/assets/temp/asm_test_01/
    current_test_temp_dir = os.path.join(config.TEMP_DIR_BASE, reel_id_test)

    # Subdirectories for dummy assets for this test
    dummy_mp3_dir = os.path.join(current_test_temp_dir, "mp3")
    dummy_img_dir = os.path.join(current_test_temp_dir, "img")
    dummy_bg_dir = os.path.join(current_test_temp_dir, "background") # For dummy raw background

    for d in [dummy_mp3_dir, dummy_img_dir, dummy_bg_dir]:
        if not os.path.exists(d):
            os.makedirs(d)

    # Dummy audio (using config settings for consistency if applicable)
    dummy_audio_path = os.path.join(dummy_mp3_dir, "dummy_speech_audio.mp3")
    # Create a silent audio file for testing
    try:
        (
            ffmpeg.input("anullsrc", format="lavfi", t=10) # 10 seconds silent audio
            .output(dummy_audio_path, acodec="mp3")
            .run(overwrite_output=True, quiet=True)
        )
        print(f"Dummy audio created at {dummy_audio_path}")
    except ffmpeg.Error as e:
        print(f"ffmpeg error creating dummy audio: {e.stderr.decode('utf8') if e.stderr else str(e)}")
        # Fallback: create empty file if ffmpeg fails (moviepy might still work for some tests)
        if not os.path.exists(dummy_audio_path): open(dummy_audio_path, 'a').close()


    # Dummy images (now using config for W, H)
    # Imagemaker itself is now config-aware, so it would generate correct size.
    # For this isolated test, we create simple placeholders.
    dummy_image_paths = []
    # Create images in this test's specific img dir: reel_creator/assets/temp/asm_test_01/img/
    # The paths passed to assemble_reel should be absolute or resolvable.
    # `main.py` passes paths from `config.ASSETS_DIR / reel_id / img / image_name.png`
    # which becomes `reel_creator/assets/temp/reel_id/img/image_name.png` if ASSETS_DIR is reel_creator/assets and TEMP_DIR_BASE is assets/temp

    # Let's use the structure imagemaker would use (relative to config.ASSETS_DIR)
    # folder_name for imagemaker is `temp/{reel_id_test}/img`
    imagemaker_style_folder_name = os.path.join("temp", reel_id_test, "img")

    try:
        # This import should work if test is run from project root or reel_creator is installed
        from reel_creator.imagenarator import imagemaker
        print("Using actual imagemaker for dummy images...")
        for i in range(3):
            # imagemaker saves into config.ASSETS_DIR / folder_name / id.png
            img_path_rel_to_assets = imagemaker(
                f"Test Image {i+1}",
                f"dummy_cfg_img_{i}",
                folder_name=imagemaker_style_folder_name # e.g. temp/asm_test_01/img
            )
            # assemble_reel expects paths that ImageClip can read.
            # imagemaker returns path like: reel_creator/assets/temp/asm_test_01/img/dummy_cfg_img_0.png
            dummy_image_paths.append(img_path_rel_to_assets)
        print(f"Dummy images created by imagemaker: {dummy_image_paths}")
    except ImportError as e:
        print(f"imagenarator not found ({e}), creating basic placeholder images in {dummy_img_dir}.")
        for i in range(3):
            img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color = (random.randint(0,255), random.randint(0,255), random.randint(0,255)))
            draw = ImageDraw.Draw(img)
            try: # Try to use a configured font for placeholders too
                font = ImageFont.truetype(config.IM_FONT_REGULAR_PATH, config.IM_FONT_SIZE)
            except IOError:
                font = ImageFont.load_default()
            draw.text((config.VIDEO_WIDTH/2, config.VIDEO_HEIGHT/2), f"Image {i+1}", fill=(255,255,255), font=font, anchor="mm")

            path = os.path.join(dummy_img_dir, f"placeholder_img_{i}.png") # Save in the test's specific img dir
            img.save(path)
            dummy_image_paths.append(path) # Add full path
        print(f"Basic placeholder images created: {dummy_image_paths}")


    # Dummy background video (16:9 for testing cropping)
    # Saved into the test's specific background dir: reel_creator/assets/temp/asm_test_01/background/
    raw_dummy_background_path = os.path.join(dummy_bg_dir, "sample_background_16_9.mp4")

    if not os.path.exists(raw_dummy_background_path):
        print(f"Creating dummy raw background video at {raw_dummy_background_path}...")
        try:
            (
                ffmpeg.input('lavfi', format='lavfi', s='1920x1080', r=str(config.VIDEO_FPS), t='15',
                             filter_complex=f'[0:v]testsrc=duration=15:size=1920x1080:rate={config.VIDEO_FPS}[outv]')
                .output(raw_dummy_background_path, vcodec=config.VIDEO_CODEC, pix_fmt='yuv420p')
                .run(overwrite_output=True, quiet=True)
            )
            print(f"Dummy 16:9 background video created at {dummy_background_path}")
        except ffmpeg.Error as e:
            print(f"ffmpeg error creating dummy 16:9 background: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            # Create an empty file as a placeholder if ffmpeg fails
            if not os.path.exists(os.path.dirname(dummy_background_path)):
                 os.makedirs(os.path.dirname(dummy_background_path))
            open(dummy_background_path, 'a').close()
            print("Created an empty placeholder for the background video.")


    if os.path.exists(dummy_audio_path) and dummy_image_paths and os.path.exists(dummy_background_path) and os.path.getsize(dummy_background_path) > 100: # Check if bg is not empty
        print("Starting reel assembly test...")
        assemble_reel(
            reel_id=reel_id_test,
            audio_path=dummy_audio_path,
            image_paths=dummy_image_paths,
            background_video_path=dummy_background_path,
            output_filename="test_config_reel.mp4", # Output name stem
            # background_is_9_16 is now taken from config by prepare_background
            # For this test, ensure config.BG_IS_ALREADY_9_16 = False to test cropping
        )
    else:
        print("Skipping reel assembly test due to missing dummy files or empty/small background video.")
        if not os.path.exists(dummy_audio_path): print(f"Missing dummy audio: {dummy_audio_path}")
        if not dummy_image_paths: print("Missing dummy images.")
        if not os.path.exists(raw_dummy_background_path): print(f"Missing raw dummy background: {raw_dummy_background_path}")
        elif os.path.exists(raw_dummy_background_path) and os.path.getsize(raw_dummy_background_path) <= 100:
            print(f"Raw dummy background video {raw_dummy_background_path} is too small or empty.")

    # Optional: Cleanup the test-specific temp directory
    # import shutil
    # if os.path.exists(current_test_temp_dir):
    #     shutil.rmtree(current_test_temp_dir)
    #     print(f"Cleaned up test directory: {current_test_temp_dir}")
