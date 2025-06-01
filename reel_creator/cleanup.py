import os
import shutil

def cleanup_temp_files(reel_id: str = None, temp_base_dir: str = "assets/temp"):
    """
    Cleans up temporary files and directories.

    If reel_id is provided, it will remove the specific directory for that reel
    (e.g., assets/temp/{reel_id}).
    If reel_id is None, it will attempt to remove the entire temp_base_dir.
    Be cautious when reel_id is None.
    """
    if reel_id:
        path_to_remove = os.path.join(temp_base_dir, str(reel_id))
        if os.path.exists(path_to_remove):
            try:
                shutil.rmtree(path_to_remove)
                print(f"Successfully removed temporary directory: {path_to_remove}")
            except OSError as e:
                print(f"Error removing directory {path_to_remove}: {e}")
        else:
            print(f"Temporary directory not found (already cleaned?): {path_to_remove}")
    else:
        # Caution: Removing the entire base temp directory.
        # This should be used carefully, e.g., at the start or end of a batch process.
        if os.path.exists(temp_base_dir):
            try:
                # Remove the directory and all its contents
                # shutil.rmtree(temp_base_dir)
                # Recreate the base temp_base_dir so it exists for next runs
                # os.makedirs(temp_base_dir, exist_ok=True)
                # For now, let's just remove contents of temp_base_dir, not the dir itself
                # if not specifically removing a reel_id.

                cleaned_count = 0
                for item_name in os.listdir(temp_base_dir):
                    item_path = os.path.join(temp_base_dir, item_name)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        elif os.path.isfile(item_path):
                            os.remove(item_path)
                        print(f"Removed: {item_path}")
                        cleaned_count +=1
                    except Exception as e:
                        print(f"Could not remove {item_path}: {e}")
                if cleaned_count > 0:
                     print(f"Cleaned contents of temporary base directory: {temp_base_dir}")
                else:
                    print(f"Temporary base directory {temp_base_dir} was empty or contents could not be removed.")

            except OSError as e:
                print(f"Error cleaning temporary base directory {temp_base_dir}: {e}")
        else:
            print(f"Temporary base directory not found: {temp_base_dir}")

if __name__ == "__main__":
    # Create some dummy files and folders for testing
    test_base = "assets/temp_cleanup_test"
    reel_id_1 = "test_reel_001"
    reel_id_2 = "test_reel_002"

    # Path for reel 1
    path_reel_1 = os.path.join(test_base, reel_id_1)
    os.makedirs(os.path.join(path_reel_1, "img"), exist_ok=True)
    os.makedirs(os.path.join(path_reel_1, "mp3"), exist_ok=True)
    with open(os.path.join(path_reel_1, "img", "image1.png"), "w") as f: f.write("dummy")
    with open(os.path.join(path_reel_1, "mp3", "audio.mp3"), "w") as f: f.write("dummy")

    # Path for reel 2
    path_reel_2 = os.path.join(test_base, reel_id_2)
    os.makedirs(path_reel_2, exist_ok=True)
    with open(os.path.join(path_reel_2, "video.mp4"), "w") as f: f.write("dummy")

    # A loose file in the test_base
    with open(os.path.join(test_base, "loose_file.txt"), "w") as f: f.write("dummy")


    print(f"Created dummy structure in: {test_base}")
    print(f"Contents of {test_base}: {os.listdir(test_base)}")
    print(f"Contents of {path_reel_1}: {os.listdir(path_reel_1)}")


    print("\n--- Test 1: Cleaning up a specific reel_id ---")
    cleanup_temp_files(reel_id=reel_id_1, temp_base_dir=test_base)
    if not os.path.exists(path_reel_1):
        print(f"SUCCESS: Directory {path_reel_1} removed.")
    else:
        print(f"FAILURE: Directory {path_reel_1} still exists.")
    if os.path.exists(path_reel_2):
        print(f"Directory {path_reel_2} correctly preserved.")
    else:
        print(f"ERROR: Directory {path_reel_2} was removed unexpectedly.")


    print("\n--- Test 2: Cleaning up the entire temp base directory (its contents) ---")
    # At this point, path_reel_1 is gone, path_reel_2 and loose_file.txt remain in test_base
    print(f"Contents of {test_base} before full cleanup: {os.listdir(test_base)}")
    cleanup_temp_files(temp_base_dir=test_base) # reel_id is None

    # Check if contents are gone
    if os.path.exists(test_base) and not os.listdir(test_base):
        print(f"SUCCESS: Contents of {test_base} removed, directory itself preserved.")
    elif not os.path.exists(test_base):
         print(f"ERROR: Base directory {test_base} was removed (should only clear contents).")
    else:
        print(f"FAILURE: Directory {test_base} still contains files: {os.listdir(test_base)}")


    print("\n--- Test 3: Cleaning a non-existent reel_id ---")
    cleanup_temp_files(reel_id="non_existent_reel", temp_base_dir=test_base)
    # Expect "Temporary directory not found" message

    print("\n--- Test 4: Cleaning a non-existent base directory ---")
    cleanup_temp_files(temp_base_dir="non_existent_base_dir")
     # Expect "Temporary base directory not found" message

    # Final cleanup of the test_base directory itself
    if os.path.exists(test_base):
        shutil.rmtree(test_base)
        print(f"\nCleaned up main test directory: {test_base}")

    print("\n--- End of cleanup.py tests ---")
