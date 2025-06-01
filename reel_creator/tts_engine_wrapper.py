from abc import ABC, abstractmethod
import os
# Possible future import from reel_config if there are global TTS settings
# from . import reel_config

class TTSEngine(ABC):
    """
    Abstract Base Class for Text-to-Speech engines.
    """

    def __init__(self, **kwargs):
        """
        Initialize the TTS engine.
        kwargs can be used for engine-specific configurations like API keys, paths, etc.
        """
        pass

    @abstractmethod
    def save_mp3(self, text: str, file_path: str, language: str = "en", **kwargs) -> float:
        """
        Generates speech from text and saves it to an MP3 file.

        Args:
            text (str): The text to convert to speech.
            file_path (str): The path where the MP3 file will be saved.
            language (str, optional): Language code for the speech (e.g., "en", "es").
                                      Defaults to "en".
            **kwargs: Additional engine-specific parameters (e.g., voice, speed, pitch).

        Returns:
            float: The duration of the generated audio in seconds.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
            Exception: Any exception that occurs during TTS generation or file saving.
        """
        # Ensure the directory for the file_path exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created directory: {output_dir}")
            except OSError as e:
                print(f"Error creating directory {output_dir}: {e}")
                # Depending on desired strictness, could raise an error here

        raise NotImplementedError("Subclasses must implement save_mp3.")

    def __str__(self):
        return self.__class__.__name__

if __name__ == "__main__":
    # This is an abstract class and cannot be instantiated directly.
    # Example of how a subclass would be defined (for illustration):

    class MyMockTTSEngine(TTSEngine):
        def save_mp3(self, text: str, file_path: str, language: str = "en", slow: bool = False, **kwargs) -> float:
            # Ensure directory exists (call to super or direct check)
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            print(f"MyMockTTSEngine: Simulating saving speech for text '{text[:50]}...' to '{file_path}' in language '{language}'.")
            # Simulate creating a file
            with open(file_path, 'w') as f:
                f.write("This is mock MP3 data.")
            # Simulate duration calculation
            duration = len(text) / 10  # Example: 10 chars per second
            print(f"MyMockTTSEngine: Estimated duration {duration}s.")
            return duration

    # Test the mock engine
    mock_engine = MyMockTTSEngine()
    test_file_path = "assets/temp/tts_wrapper_test/mock_speech.mp3"

    # Clean up previous test file if it exists
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    if os.path.exists(os.path.dirname(test_file_path)) and not os.listdir(os.path.dirname(test_file_path)):
        os.rmdir(os.path.dirname(test_file_path))
    if os.path.exists(os.path.dirname(os.path.dirname(test_file_path))) and not os.listdir(os.path.dirname(os.path.dirname(test_file_path))):
         os.rmdir(os.path.dirname(os.path.dirname(test_file_path)))


    print(f"Testing {mock_engine}...")
    try:
        # The TTSEngine itself will try to create the directory if save_mp3 from parent is called BEFORE the check.
        # However, the mock implementation also has its own check.
        # To test TTSEngine's directory creation, a direct call to a hypothetical parent save_mp3 would be needed,
        # or ensure the mock calls super().save_mp3() which then raises NotImplementedError.
        # For now, the mock's own directory creation is what's primarily tested.

        # First, test if directory creation within save_mp3 works
        if os.path.exists(test_file_path): os.remove(test_file_path)
        if os.path.exists(os.path.dirname(test_file_path)): os.rmdir(os.path.dirname(test_file_path))

        duration = mock_engine.save_mp3("Hello world, this is a test.", test_file_path, language="en-us")
        if os.path.exists(test_file_path):
            print(f"Test file created at {test_file_path} with duration {duration}s.")
            # Clean up
            os.remove(test_file_path)
            os.rmdir(os.path.dirname(test_file_path)) # remove tts_wrapper_test
            if os.path.exists("assets/temp") and not os.listdir("assets/temp"): # remove temp if empty
                os.rmdir("assets/temp")
            if os.path.exists("assets") and not os.listdir("assets"): # remove assets if empty
                 os.rmdir("assets")

        else:
            print(f"ERROR: Test file {test_file_path} was not created by mock engine.")

    except Exception as e:
        print(f"Error during mock engine test: {e}")

    # Test the abstract method directly (should fail)
    print("\nTesting direct instantiation of TTSEngine (should fail):")
    try:
        engine = TTSEngine()
        # The following line would only be reached if __init__ doesn't prevent instantiation or if it's not abstract.
        # engine.save_mp3("text", "file.mp3")
    except TypeError as e:
        print(f"Successfully caught error for abstract class instantiation: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
