import os
from gtts import gTTS
from mutagen.mp3 import MP3
from .tts_engine_wrapper import TTSEngine
# from . import reel_config # For potential future config like default language

class GTTS(TTSEngine):
    """
    gTTS implementation for Text-to-Speech.
    """

    def __init__(self, **kwargs):
        """
        Initializes the gTTS engine.
        kwargs are not strictly used by gTTS constructor but kept for consistency.
        """
        super().__init__(**kwargs)
        # gTTS doesn't require much initialization here, API keys are not needed.

    def save_mp3(self, text: str, file_path: str, language: str = "en", slow: bool = False, tld: str = "com", **kwargs) -> float:
        """
        Generates speech from text using gTTS and saves it to an MP3 file.

        Args:
            text (str): The text to convert to speech.
            file_path (str): The path where the MP3 file will be saved.
            language (str, optional): Language code for the speech (e.g., "en", "fr").
                                      Defaults to "en".
            slow (bool, optional): Whether to use a slower speech rate. Defaults to False.
            tld (str, optional): Top-level domain for gTTS (e.g., "com", "co.uk").
                                 This can affect accent/voice. Defaults to "com".
            **kwargs: Additional arguments (not used by gTTS directly in this method but kept for signature consistency).

        Returns:
            float: The duration of the generated audio in seconds.

        Raises:
            gTTSError: If gTTS fails to generate speech.
            Exception: For file saving errors or other issues.
        """
        # Ensure the output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory for MP3: {output_dir}")

        try:
            tts = gTTS(text=text, lang=language, slow=slow, tld=tld)
            tts.save(file_path)
            print(f"gTTS: Successfully saved speech for '{text[:50]}...' to '{file_path}'")
        except Exception as e:
            print(f"gTTS error: {e}")
            raise # Re-raise the exception to be handled by the caller

        try:
            audio = MP3(file_path)
            duration = audio.info.length
            return duration
        except Exception as e:
            print(f"Error reading MP3 duration for {file_path}: {e}")
            # Fallback: if duration can't be read, return 0.0 or raise error
            # For now, returning 0.0 and logging it. A more robust solution might be needed.
            return 0.0


if __name__ == "__main__":
    # Create a temporary directory for testing
    test_reel_id = "gtts_engine_test"
    temp_output_dir = f"assets/temp/{test_reel_id}/mp3"

    if not os.path.exists(temp_output_dir):
        os.makedirs(temp_output_dir)

    gtts_engine = GTTS()

    test_text_1 = "Hello from the gTTS engine. This is a standard test in English."
    test_file_1 = os.path.join(temp_output_dir, "test_speech_1.mp3")

    test_text_2 = "Ceci est un test en français avec une vitesse normale."
    test_file_2 = os.path.join(temp_output_dir, "test_speech_2_fr.mp3")

    test_text_3 = "This is a slow version of English speech."
    test_file_3 = os.path.join(temp_output_dir, "test_speech_3_slow.mp3")

    print(f"Testing {gtts_engine}...")

    try:
        print(f"\nTest 1: Standard English")
        duration1 = gtts_engine.save_mp3(test_text_1, test_file_1, language="en")
        if os.path.exists(test_file_1):
            print(f"SUCCESS: File '{test_file_1}' created. Duration: {duration1:.2f}s")
        else:
            print(f"FAILURE: File '{test_file_1}' was NOT created.")

        print(f"\nTest 2: French")
        duration2 = gtts_engine.save_mp3(test_text_2, test_file_2, language="fr")
        if os.path.exists(test_file_2):
            print(f"SUCCESS: File '{test_file_2}' created. Duration: {duration2:.2f}s")
        else:
            print(f"FAILURE: File '{test_file_2}' was NOT created.")

        print(f"\nTest 3: Slow English")
        duration3 = gtts_engine.save_mp3(test_text_3, test_file_3, language="en", slow=True)
        if os.path.exists(test_file_3):
            print(f"SUCCESS: File '{test_file_3}' created. Duration: {duration3:.2f}s")
        else:
            print(f"FAILURE: File '{test_file_3}' was NOT created.")

        print(f"\nTest 4: Invalid language (expected to fail gracefully or be caught by gTTS)")
        try:
            gtts_engine.save_mp3("Test invalid lang", os.path.join(temp_output_dir, "test_invalid.mp3"), language="xxxyyy")
        except Exception as e:
            print(f"CAUGHT EXPECTED EXCEPTION for invalid language: {e}")


    except Exception as e:
        print(f"An error occurred during gTTS engine tests: {e}")
    finally:
        print("\nCleaning up test files (commented out for inspection):")
        # for f in [test_file_1, test_file_2, test_file_3]:
        #     if os.path.exists(f):
        #         os.remove(f)
        # if os.path.exists(os.path.join(temp_output_dir, "test_invalid.mp3")):
        #     os.remove(os.path.join(temp_output_dir, "test_invalid.mp3"))
        # if os.path.exists(temp_output_dir) and not os.listdir(temp_output_dir):
        #     os.rmdir(temp_output_dir)
        # parent_dir = os.path.dirname(temp_output_dir)
        # if os.path.exists(parent_dir) and not os.listdir(parent_dir):
        #     os.rmdir(parent_dir) # remove test_reel_id folder
        pass # Keep files for now.

    # Example of how it would be used via reel_tts.py (if reel_tts.py is in place and runnable)
    # This part might fail if reel_tts.py has pathing issues for its imports at this stage
    print("\n--- Simulating call via reel_tts.py ---")
    try:
        # To make this work, ensure reel_tts.py can find tts_engine_wrapper and gtts_engine
        # This might require adding reel_creator to sys.path or using `python -m reel_creator.reel_tts`
        # For this isolated test, we assume paths resolve correctly.
        from reel_creator.reel_tts import save_text_to_mp3

        tts_reel_test_file = os.path.join(temp_output_dir, "reel_tts_gtts_test.mp3")
        save_text_to_mp3(
            reel_id=test_reel_id,
            text="Testing gTTS via the main save_text_to_mp3 function.",
            filename="reel_tts_gtts_test.mp3", # filename part of path
            output_dir=temp_output_dir, # specify full dir
            tts_provider="gTTS", # Explicitly select gTTS
            language="en-gb", # Test a tld variant if gTTS handles it via lang
            tld="co.uk" # More direct way for gTTS tld
        )
        if os.path.exists(tts_reel_test_file):
            print(f"SUCCESS: File '{tts_reel_test_file}' created via save_text_to_mp3.")
        else:
            print(f"FAILURE: File '{tts_reel_test_file}' was NOT created via save_text_to_mp3.")

    except ImportError as ie:
        print(f"Could not import from reel_tts.py for integrated test: {ie}. This is expected if paths are not yet set up.")
    except Exception as e:
        print(f"Error during simulated call via reel_tts: {e}")

    print("--- End of gtts_engine.py tests ---")
