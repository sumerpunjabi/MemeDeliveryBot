import os
from typing import Type, Optional
from .tts_engine_wrapper import TTSEngine
from .gtts_engine import GTTS
# from .another_tts_engine import AnotherTTS # Example for future expansion
from . import reel_config as config # Import main configuration

# Available TTS providers within this module
# Key: User-friendly name (should match TTS_PROVIDER in config)
# Value: The class implementing TTSEngine
TTS_PROVIDERS_MAP: dict[str, Type[TTSEngine]] = {
    "gTTS": GTTS,
    # "pyttsx3": PyttsxEngine, # Example if added
    # "elevenlabs": ElevenLabsEngine, # Example if added
}

def get_tts_engine(provider_name_override: Optional[str] = None) -> TTSEngine:
    """
    Returns an instance of the specified TTS engine.
    If provider_name_override is given, it's used.
    Otherwise, defaults to `config.TTS_PROVIDER`.
    Initializes the engine with parameters from `config.TTS_VOICE_PARAMS`.
    """
    provider_to_use = provider_name_override or config.TTS_PROVIDER

    if provider_to_use in TTS_PROVIDERS_MAP:
        engine_class = TTS_PROVIDERS_MAP[provider_to_use]
        # Pass relevant voice parameters from config to the engine's constructor
        # The engine's __init__ should be designed to accept these or **kwargs
        engine_params = config.TTS_VOICE_PARAMS.get(provider_to_use, {}) # Get params specific to this provider

        # For gTTS, specific params like 'tld' or 'slow' are handled in save_mp3.
        # For others like ElevenLabs, API key might be passed here.
        # Example: if provider_to_use == "elevenlabs":
        #    engine_params['api_key'] = config.TTS_VOICE_PARAMS.get("ELEVENLABS_API_KEY")
        try:
            return engine_class(**engine_params)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize TTS engine '{provider_to_use}' with params {engine_params}: {e}")

    else:
        raise ValueError(
            f"TTS provider '{provider_to_use}' not found or not configured in TTS_PROVIDERS_MAP. "
            f"Available and configured: {list(TTS_PROVIDERS_MAP.keys())}"
        )

def save_text_to_mp3(
    reel_id: str, # Used for structuring temp save paths
    text: str,
    filename: str = "speech.mp3", # Filename stem for the MP3
    output_dir: Optional[str] = None, # Full path to output directory
    # Parameters below can override config settings if provided directly
    tts_provider_override: Optional[str] = None,
    language_override: Optional[str] = None,
    # Provider-specific kwargs can be passed, these might also override parts of TTS_VOICE_PARAMS
    **provider_kwargs
) -> tuple[str, float]:
    """
    Generates speech from text using the configured TTS provider and saves it to an MP3 file.
    Settings from reel_config.py are used by default but can be overridden by parameters.
    Returns the path to the saved MP3 file and its duration in seconds.
    """
    # Determine final parameters, prioritizing function arguments over config
    actual_tts_provider = tts_provider_override or config.TTS_PROVIDER
    actual_language = language_override or config.TTS_LANGUAGE

    # Base temporary directory for this reel's audio
    if not output_dir:
        # Default to reel_creator/assets/temp/{reel_id}/mp3
        mp3_output_base_dir = os.path.join(config.TEMP_DIR_BASE, reel_id, "mp3")
    else:
        mp3_output_base_dir = output_dir

    if not os.path.exists(mp3_output_base_dir):
        os.makedirs(mp3_output_base_dir)
        print(f"Created TTS output directory: {mp3_output_base_dir}")

    engine = get_tts_engine(actual_tts_provider) # Engine initialized with general params from config

    # Prepare provider-specific parameters for the save_mp3 call
    # Merge general voice params from config with any direct kwargs
    # Direct kwargs take precedence
    final_provider_params = {**config.TTS_VOICE_PARAMS.get(actual_tts_provider, {}), **provider_kwargs}

    # For gTTS, 'slow' and 'tld' are primary direct params.
    # These might be in TTS_VOICE_PARAMS (e.g., "gTTS_slow": True) or passed via provider_kwargs
    if actual_tts_provider == "gTTS":
        # Ensure 'slow' and 'tld' are correctly passed if they exist in final_provider_params
        # The gtts_engine.save_mp3 expects 'slow' and 'tld' as direct arguments.
        gtts_specific_params = {}
        if 'gTTS_slow' in final_provider_params: # Check for config-style key
            gtts_specific_params['slow'] = final_provider_params['gTTS_slow']
        if 'slow' in final_provider_params: # Check for direct kwarg
             gtts_specific_params['slow'] = final_provider_params['slow']

        if 'gTTS_tld' in final_provider_params:
            gtts_specific_params['tld'] = final_provider_params['gTTS_tld']
        if 'tld' in final_provider_params:
            gtts_specific_params['tld'] = final_provider_params['tld']

        # Update final_provider_params to only include what the engine method expects,
        # or ensure the engine method can handle extra kwargs gracefully.
        # For gTTS, we explicitly pass known params.
        final_provider_params = gtts_specific_params


    output_filepath = os.path.join(mp3_output_base_dir, filename)

    try:
        # TTSEngine's save_mp3 method signature: text, file_path, language, **kwargs
        duration = engine.save_mp3(
            text,
            output_filepath,
            language=actual_language,
            **final_provider_params # Pass merged and filtered params
        )
        print(f"Speech successfully saved to {output_filepath}, duration: {duration:.2f}s using {actual_tts_provider}")
        return output_filepath, duration
    except Exception as e:
        print(f"Error generating speech with {engine.__class__.__name__} for file {output_filepath}: {e}")
        # Consider logging the full traceback here for debugging
        # import traceback
        # traceback.print_exc()
        raise # Re-raise the exception to be handled by the caller

if __name__ == "__main__":
    print("--- Testing Reel TTS with Config ---")

    # Ensure TEMP_DIR_BASE exists for the test, as save_text_to_mp3 relies on it
    if not os.path.exists(config.TEMP_DIR_BASE):
        os.makedirs(config.TEMP_DIR_BASE)
        print(f"Created base temp directory for test: {config.TEMP_DIR_BASE}")

    test_reel_id_config = "tts_config_test_01"
    # output_dir for this test will be config.TEMP_DIR_BASE / test_reel_id_config / "mp3"
    # This is constructed internally by save_text_to_mp3 if output_dir is None.

    # Test using default provider from config (expected to be gTTS)
    print(f"\nTesting with TTS provider from config (expected: {config.TTS_PROVIDER})...")
    text1 = "Hello from reel_tts, using settings from reel_config."
    try:
        mp3_path1, duration1 = save_text_to_mp3(
            reel_id=test_reel_id_config,
            text=text1,
            filename="test_config_default.mp3"
            # No tts_provider_override, so it uses config.TTS_PROVIDER
            # No language_override, so it uses config.TTS_LANGUAGE
            # Other params like 'slow' or 'tld' for gTTS come from config.TTS_VOICE_PARAMS
        )
        print(f"Saved to {mp3_path1}, Duration: {duration1:.2f}s. File exists: {os.path.exists(mp3_path1)}")
    except Exception as e:
        print(f"Error during TTS test with config defaults: {e}")
        print("Ensure gTTS is installed and internet is available if using gTTS.")

    # Test overriding language and gTTS 'tld' (if provider is gTTS)
    if config.TTS_PROVIDER == "gTTS":
        print(f"\nTesting with gTTS, overriding language and tld...")
        text2 = "This is a test in UK English accent."
        try:
            mp3_path2, duration2 = save_text_to_mp3(
                reel_id=test_reel_id_config,
                text=text2,
                filename="test_gtts_override.mp3",
                language_override="en", # Explicitly 'en'
                tld="co.uk" # Pass 'tld' directly as a kwarg for gTTS
            )
            print(f"Saved to {mp3_path2}, Duration: {duration2:.2f}s. File exists: {os.path.exists(mp3_path2)}")
        except Exception as e:
            print(f"Error during gTTS override test: {e}")

    # Test with a non-existent provider override
    print("\nTesting with a non-existent provider override (expected to fail)...")
    text3 = "This should fail."
    try:
        save_text_to_mp3(
            reel_id=test_reel_id_config,
            text=text3,
            filename="test_fail_provider.mp3",
            tts_provider_override="InvalidTTSProvider"
        )
    except ValueError as e:
        print(f"Caught expected ValueError for invalid provider: {e}")
    except Exception as e:
        print(f"Caught unexpected error for invalid provider: {e}")

    print("\n--- Reel TTS Test Complete ---")
    print(f"Check temporary files in subdirectories of: {config.TEMP_DIR_BASE}/{test_reel_id_config}")
    # Example cleanup (optional, comment out to inspect files):
    # import shutil
    # test_output_folder = os.path.join(config.TEMP_DIR_BASE, test_reel_id_config)
    # if os.path.exists(test_output_folder):
    #     shutil.rmtree(test_output_folder)
    #     print(f"Cleaned up test folder: {test_output_folder}")
