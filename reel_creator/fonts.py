import os

# Define a base directory for fonts if they are packaged with the module
# This could also point to system fonts or a user-configured path.
_DEFAULT_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")

# Store a dictionary of available fonts, mapping a friendly name to a file path.
# This can be expanded or loaded from a configuration file.
AVAILABLE_FONTS = {
    "verdana_bold": os.path.join(_DEFAULT_FONTS_DIR, "verdanab.ttf"),
    "arial": os.path.join(_DEFAULT_FONTS_DIR, "arial.ttf"), # Example, if arial.ttf is available
    # Add more fonts here as needed
}

def get_font_path(font_name: str) -> str:
    """
    Retrieves the full path to a font file by its friendly name.

    Args:
        font_name (str): The friendly name of the font (e.g., "verdana_bold").

    Returns:
        str: The absolute path to the font file.

    Raises:
        FileNotFoundError: If the font_name is not found or the file doesn't exist.
    """
    font_path = AVAILABLE_FONTS.get(font_name.lower())

    if not font_path:
        raise FileNotFoundError(f"Font '{font_name}' not recognized. Available fonts: {list(AVAILABLE_FONTS.keys())}")

    # Check if the font file actually exists at the specified path.
    # This is important if paths are configured or could change.
    if not os.path.exists(font_path):
        # Try to resolve relative to a base directory if it's not absolute
        # This logic might need adjustment based on how FONT_PATH in imagenarator is handled
        if not os.path.isabs(font_path):
             resolved_path = os.path.abspath(os.path.join(_DEFAULT_FONTS_DIR, os.path.basename(font_path)))
             if os.path.exists(resolved_path):
                 AVAILABLE_FONTS[font_name.lower()] = resolved_path # Update cache
                 font_path = resolved_path
             else:
                raise FileNotFoundError(f"Font file for '{font_name}' not found at expected path: {font_path} or {resolved_path}")
        else:
            raise FileNotFoundError(f"Font file for '{font_name}' not found at specified absolute path: {font_path}")

    return font_path

def get_default_font_path() -> str:
    """
    Returns the path to a default font.
    """
    # For now, returning "verdana_bold" as default. This could be made configurable.
    try:
        return get_font_path("verdana_bold")
    except FileNotFoundError:
        # Fallback if verdana_bold is not found (e.g., assets not available)
        print("Warning: Default font 'verdanab.ttf' not found. Attempting to find any available font.")
        if AVAILABLE_FONTS:
            # Try the first available font as a last resort
            first_available = list(AVAILABLE_FONTS.keys())[0]
            print(f"Falling back to first available font: {first_available}")
            try:
                return get_font_path(first_available)
            except FileNotFoundError as e:
                print(f"Critical: Fallback font '{first_available}' also not found: {e}")
                # This is a critical issue, as no fonts are available.
                # Depending on Pillow's capabilities, it might use a very basic built-in font,
                # or text rendering will fail.
                raise FileNotFoundError("No usable fonts found. Please check font configuration and paths.") from e
        else:
            raise FileNotFoundError("No fonts configured in AVAILABLE_FONTS and default is missing.")


if __name__ == "__main__":
    print("Available fonts:")
    for name, path in AVAILABLE_FONTS.items():
        exists = os.path.exists(path)
        # Try to resolve if not exists and relative
        if not exists and not os.path.isabs(path):
            path = os.path.abspath(os.path.join(_DEFAULT_FONTS_DIR, os.path.basename(path)))
            exists = os.path.exists(path)
        print(f"  - {name}: {path} (Exists: {exists})")

    print("\nTesting get_font_path:")
    try:
        # Assuming 'verdanab.ttf' is in 'assets/fonts/' relative to the bot's root
        # For this test, we need to ensure the pathing is correct relative to where this script runs.
        # The _DEFAULT_FONTS_DIR is defined as reel_creator/../assets/fonts = assets/fonts

        # Create a dummy font file for testing if it doesn't exist
        # This makes the test self-contained for path resolution.
        dummy_font_dir = _DEFAULT_FONTS_DIR
        dummy_verdana_path = os.path.join(dummy_font_dir, "verdanab.ttf")

        if not os.path.exists(dummy_verdana_path):
            print(f"\nNOTE: '{dummy_verdana_path}' not found. Creating a dummy file for testing.")
            os.makedirs(dummy_font_dir, exist_ok=True)
            with open(dummy_verdana_path, "w") as f:
                f.write("dummy font data")
            created_dummy = True
        else:
            created_dummy = False

        print(f"Path for 'verdana_bold': {get_font_path('verdana_bold')}")
        print(f"Default font path: {get_default_font_path()}")

        if created_dummy:
            os.remove(dummy_verdana_path)
            print(f"Cleaned up dummy font file: {dummy_verdana_path}")
            # Attempt to clean up dirs if empty
            if not os.listdir(dummy_font_dir): os.rmdir(dummy_font_dir)
            if os.path.basename(dummy_font_dir) == "fonts" and \
               os.path.exists(os.path.dirname(dummy_font_dir)) and \
               not os.listdir(os.path.dirname(dummy_font_dir)):
                os.rmdir(os.path.dirname(dummy_font_dir)) # remove 'assets' if empty

    except FileNotFoundError as e:
        print(f"Error retrieving font: {e}")
        print("Ensure 'verdanab.ttf' (or a dummy) is in the correct 'assets/fonts' directory relative to the project root.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print("\nTesting non-existent font:")
    try:
        get_font_path("non_existent_font")
    except FileNotFoundError as e:
        print(f"Caught expected error: {e}")

    # Test case where AVAILABLE_FONTS might have a bad path initially
    print("\nTesting recovery of relative path:")
    original_verdana_path = AVAILABLE_FONTS.get("verdana_bold")
    AVAILABLE_FONTS["verdana_bold"] = "verdanab.ttf" # Simulate a relative, non-existent path initially

    # Re-create dummy if it was cleaned up
    created_dummy_again = False
    if not os.path.exists(dummy_verdana_path):
        os.makedirs(dummy_font_dir, exist_ok=True)
        with open(dummy_verdana_path, "w") as f: f.write("dummy font data")
        created_dummy_again = True

    try:
        resolved_path = get_font_path("verdana_bold")
        print(f"Resolved path for 'verdana_bold' (relative test): {resolved_path}")
        if os.path.isabs(resolved_path) and os.path.exists(resolved_path):
            print("SUCCESS: Relative path resolved correctly.")
        else:
            print(f"FAILURE: Path {resolved_path} is not absolute or does not exist.")
    except FileNotFoundError as e:
        print(f"Error in relative path test: {e}")
    finally:
        if original_verdana_path: # Restore original path for consistency
             AVAILABLE_FONTS["verdana_bold"] = original_verdana_path
        if created_dummy_again:
            os.remove(dummy_verdana_path)
            if not os.listdir(dummy_font_dir): os.rmdir(dummy_font_dir)

    print("--- End of fonts.py tests ---")
