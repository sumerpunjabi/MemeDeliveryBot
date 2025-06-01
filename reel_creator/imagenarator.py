import os
from PIL import Image, ImageDraw, ImageFont

# Assuming utils.text_wrap will be available or adapted.
# If it's part of this project, its path might need adjustment e.g. from ..utils.text_wrap
# For now, we'll keep the import as is, assuming it's resolvable in the execution environment.
try:
    from utils.text_wrap import draw_multiple_line_text
except ImportError:
    # Fallback or placeholder if text_wrap is not found
    print("Warning: utils.text_wrap not found. draw_multiple_line_text might not be available.")
    print("Attempting to use a basic text drawing fallback for imagemaker.")
    def draw_multiple_line_text(draw, text, font, text_color, wrap, xy, anchor="mm", **kwargs):
        # Basic fallback: does not wrap text, just draws it.
        # Real implementation should handle text wrapping properly.
        print("WARNING: Using basic text draw (no wrap). For proper wrapping, ensure utils.text_wrap.draw_multiple_line_text is available.")
        draw.text(xy, text, font=font, fill=text_color, anchor=anchor)


from . import reel_config as config # Import the configuration

def imagemaker(
    text: str,
    id: str,
    folder_name: str, # Expects full path like assets/temp/{reel_id}/img
    is_title: bool = False, # Optional: To use different font settings for title
    # Allow overriding config settings via parameters if needed for flexibility
    font_path_override: str = None,
    font_size_override: int = None,
    text_color_override: str = None,
    bg_color_override: str = None,
    wrap_width_override: int = None
) -> str:
    """
    Generates an image with the given text, configured via reel_config.py.
    Saves images to a subfolder within the reel_id's temp directory.
    e.g., assets/temp/reel123/img/img_title.png
    """
    # Determine output path for images for this specific reel_id
    # folder_name here is expected to be like "reel_id/img" and will be joined with TEMP_DIR_BASE
    # However, the calling function `generate_reel` in `main.py` does:
    # `folder_name=os.path.join(reel_id, "img")` which is then used as `assets/{folder_name}/img`
    # This leads to `assets/reel_id/img/img`. This needs to be consistent.
    # Let's assume `folder_name` is the direct path where images should be saved.
    # So, `main.py` should construct `os.path.join(current_reel_temp_dir, "img")` and pass it.

    # For clarity and consistency:
    # `base_save_dir` should be `config.TEMP_DIR_BASE`.
    # `reel_specific_img_dir` = `os.path.join(base_save_dir, reel_id, "img")`
    # `imagemaker` should then take `reel_id` and `image_filename_stem` (e.g. "img_title")
    # For now, adapting to current call from main.py: `folder_name` is `reel_id/img`
    # and the function prepends `config.ASSETS_DIR` (which is `reel_creator/assets`)

    # Corrected path logic:
    # main.py passes folder_name as "{reel_id}/img"
    # imagemaker saves into config.ASSETS_DIR / folder_name
    # So, assets_dir = config.ASSETS_DIR (e.g. /path/to/project/reel_creator/assets)
    # final_image_dir = os.path.join(assets_dir, folder_name)

    final_image_dir = os.path.join(config.ASSETS_DIR, folder_name)
    if not os.path.exists(final_image_dir):
        os.makedirs(final_image_dir)
        print(f"Imagemaker created directory: {final_image_dir}")

    # Use settings from reel_config
    video_width = config.VIDEO_WIDTH
    video_height = config.VIDEO_HEIGHT

    font_regular_path = font_path_override or (config.IM_FONT_BOLD_PATH if is_title else config.IM_FONT_REGULAR_PATH)
    font_size = font_size_override or (config.IM_TITLE_FONT_SIZE if is_title else config.IM_FONT_SIZE)
    text_color = text_color_override or config.IM_TEXT_COLOR

    # Background color for the image slide itself (not the text box background)
    # If IM_BACKGROUND_COLOR is "none" or None, make image transparent
    img_bg_color_config = config.IM_BACKGROUND_COLOR
    image_mode = "RGBA" if img_bg_color_config is None or str(img_bg_color_config).lower() == "none" else "RGB"

    if image_mode == "RGBA" and (img_bg_color_config is None or str(img_bg_color_config).lower() == "none"):
        # Fully transparent background for the image itself
        img_pil_bg_color = (0, 0, 0, 0)
    elif isinstance(img_bg_color_config, str) and img_bg_color_config.startswith("rgba"):
        # Config uses rgba string, convert to tuple for Pillow
        try:
            parts = img_bg_color_config.replace("rgba(", "").replace(")", "").split(',')
            img_pil_bg_color = tuple(map(int, parts))
            image_mode = "RGBA" # Ensure RGBA mode if alpha is present
        except ValueError:
            print(f"Warning: Invalid RGBA background color string '{img_bg_color_config}'. Defaulting to black.")
            img_pil_bg_color = "black" # Fallback
            image_mode = "RGB"
    else: # Handles hex strings like #FFFFFF or color names like "black" for RGB
        img_pil_bg_color = img_bg_color_config if image_mode == "RGB" else "black"


    wrap_width = wrap_width_override or config.IM_TEXT_WRAP_WIDTH

    size = (video_width, video_height)
    img = Image.new(image_mode, size, color=img_pil_bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(font_regular_path, font_size)
    except IOError:
        print(f"Font not found at {font_regular_path} (or fallback {config.IM_FONT_REGULAR_PATH}). Using default system font.")
        try:
            font = ImageFont.load_default(size=font_size) # Try to get default with requested size
        except AttributeError: # Older Pillow versions might not support size for load_default
            font = ImageFont.load_default()


    # Text rendering details
    # The draw_multiple_line_text function is assumed to handle text box background color if needed.
    # Current config.IM_BACKGROUND_COLOR is for the whole image slide.
    # If a *text box* needs a different background, that's a feature for draw_multiple_line_text.

    # Centering text on the image
    text_x = video_width / 2
    text_y = video_height / 2

    # The `draw_multiple_line_text` should ideally handle text box background color, padding etc.
    # For now, it just draws text. If it needs a text_box_color param, it would come from config.
    draw_multiple_line_text(
        draw,
        text,
        font=font,
        text_color=text_color,
        wrap=wrap_width,
        xy=(text_x, text_y),
        anchor="mm" # Middle-middle anchor for text
        # text_box_color=config.IM_TEXT_BOX_BACKGROUND_COLOR, # if this feature exists
        # padding=config.IM_TEXT_BOX_PADDING # if this feature exists
    )

    image_path = os.path.join(final_image_dir, f"{id}.png")
    img.save(image_path)
    # print(f"Image saved to {image_path}") # Reduce verbosity, main.py can log this
    return image_path

if __name__ == "__main__":
    print("--- Testing Imagemaker with Config ---")

    # Ensure config paths are valid for test or provide fallbacks
    # Dummy config values if reel_config itself is not fully set up for a direct run
    class MockConfig:
        VIDEO_WIDTH = 1080
        VIDEO_HEIGHT = 1920
        # Use paths relative to this file for test if reel_config's paths are complex
        # For this test, we assume reel_config.py has valid paths to dummy fonts created earlier
        # like reel_creator/assets/fonts/Roboto-Regular.ttf
        _fonts_dir = os.path.join(os.path.dirname(__file__), 'assets', 'fonts')
        IM_FONT_REGULAR_PATH = os.path.join(_fonts_dir, "Roboto-Regular.ttf")
        IM_FONT_BOLD_PATH = os.path.join(_fonts_dir, "Roboto-Bold.ttf")
        IM_FONT_SIZE = 50
        IM_TITLE_FONT_SIZE = 65
        IM_TEXT_COLOR = "#E0E0E0"
        IM_BACKGROUND_COLOR = "rgba(30,30,30,0.8)" # Dark semi-transparent
        IM_TEXT_WRAP_WIDTH = 28
        ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets") # reel_creator/assets

    # Replace actual config with mock for isolated testing if necessary
    # For this run, we assume reel_config is importable and its paths are fine.
    # config = MockConfig # Uncomment to use MockConfig for testing this file directly

    # Create dummy fonts if they don't exist, using paths from actual config
    if not os.path.exists(config.IM_FONT_REGULAR_PATH):
        os.makedirs(os.path.dirname(config.IM_FONT_REGULAR_PATH), exist_ok=True)
        with open(config.IM_FONT_REGULAR_PATH, "w") as f: f.write("dummy font")
        print(f"Created dummy font for test: {config.IM_FONT_REGULAR_PATH}")
    if not os.path.exists(config.IM_FONT_BOLD_PATH):
        os.makedirs(os.path.dirname(config.IM_FONT_BOLD_PATH), exist_ok=True)
        with open(config.IM_FONT_BOLD_PATH, "w") as f: f.write("dummy font")
        print(f"Created dummy font for test: {config.IM_FONT_BOLD_PATH}")

    # Base directory for test outputs (e.g., reel_creator/assets/temp_imagemaker_test/test_reel_id/img)
    # This should align with how `main.py` structures temp folders.
    # `main.py` uses `config.TEMP_DIR_BASE` which is `reel_creator/assets/temp`
    # then `reel_id/img` under that.
    test_reel_id = "img_test_001"
    # `folder_name_for_imagemaker` is the part *after* `config.ASSETS_DIR`
    # So it should be `temp/{test_reel_id}/img`
    folder_name_for_imagemaker = os.path.join("temp", test_reel_id, "img")

    # Full path for verification, though imagemaker constructs it internally
    full_test_output_dir = os.path.join(config.ASSETS_DIR, folder_name_for_imagemaker)
    if not os.path.exists(full_test_output_dir):
        os.makedirs(full_test_output_dir)
    print(f"Test images will be saved in: {full_test_output_dir}")


    example_text_title = "This is a Title Test for Reel Imagemaker using Config."
    title_img_path = imagemaker(
        text=example_text_title,
        id="test_title_img",
        folder_name=folder_name_for_imagemaker,
        is_title=True
    )
    print(f"Title image saved to: {title_img_path} (Exists: {os.path.exists(title_img_path)})")

    example_text_body = "This is a longer body text. It should wrap according to the IM_TEXT_WRAP_WIDTH set in reel_config. The background color, font, and text color are also from config."
    body_img_path = imagemaker(
        text=example_text_body,
        id="test_body_img",
        folder_name=folder_name_for_imagemaker,
        is_title=False
    )
    print(f"Body image saved to: {body_img_path} (Exists: {os.path.exists(body_img_path)})")

    # Test with "none" background
    original_bg_color = config.IM_BACKGROUND_COLOR
    config.IM_BACKGROUND_COLOR = "none"
    print(f"\nTesting with transparent background (IM_BACKGROUND_COLOR = 'none')")
    transparent_img_path = imagemaker(
        text="Transparent BG Test",
        id="test_transparent_img",
        folder_name=folder_name_for_imagemaker
    )
    print(f"Transparent BG image saved to: {transparent_img_path} (Exists: {os.path.exists(transparent_img_path)})")
    # Check if it's RGBA
    try:
        img = Image.open(transparent_img_path)
        print(f"Transparent image mode: {img.mode}")
        if img.mode != "RGBA":
            print("ERROR: Transparent image does not have RGBA mode!")
    except Exception as e:
        print(f"Error opening/checking transparent image: {e}")
    config.IM_BACKGROUND_COLOR = original_bg_color # Restore


    print("\n--- Imagemaker Test Complete ---")
    print(f"Please check the directory: {full_test_output_dir}")
    # Consider cleanup: shutil.rmtree(os.path.join(config.ASSETS_DIR, "temp", test_reel_id))
