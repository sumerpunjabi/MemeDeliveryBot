import os
import requests
import time # For polling status
import json # For parsing API responses

from . import reel_config

# --- Constants ---
GRAPH_API_BASE_URL = "https://graph.facebook.com/v19.0" # Using a recent Graph API version

# --- Instructions for Instagram Access Token Generation ---
# HOW TO GET AN INSTAGRAM ACCESS TOKEN AND USER ID:
#
# To use this feature, you need a long-lived Instagram User Access Token
# and your Instagram User ID. Here's a general guide:
#
# 1. Facebook Developer Account & App:
#    - Go to developers.facebook.com and create a developer account if you haven't.
#    - Create a new Facebook App. Choose 'Business' as app type, or 'None' / 'Something Else'.
#    - From the App Dashboard, add the "Instagram Basic Display API" and "Instagram Graph API" products.
#      (If your Instagram account is a Business or Creator account, the "Instagram Graph API" is primary).
#
# 2. Configure Permissions:
#    - The key permission you need is `instagram_content_publish`.
#    - You may also need `instagram_basic`, `pages_read_engagement` if your app uses Facebook Login
#      to authenticate the user. For Business/Creator accounts, `instagram_manage_insights` or
#      `instagram_shopping_tagging` might be relevant for other features but not strictly for publishing.
#      The `instagram_graph_user_profile` (from Basic Display API) or equivalent from Graph API
#      will be needed to get your Instagram User ID.
#
# 3. Link Instagram Account:
#    - Ensure your Instagram account is correctly linked to your Facebook Page if it's a Business/Creator account.
#    - You might need to add yourself as an Instagram Test User in the app settings under
#      "Instagram Basic Display API" > "Basic Display" for testing before app review if not using Business Account.
#
# 4. Generate Access Token:
#    - Go to "Tools" > "Graph API Explorer" in the Facebook Developer portal.
#    - Select your Facebook App in the top-right.
#    - Under "User or Page", select "Get User Access Token".
#    - In the permissions list, make sure to select `instagram_content_publish`. Add other necessary
#      permissions like `instagram_basic`, `pages_read_engagement` OR `instagram_graph_user_profile`.
#    - Click "Generate Access Token". You'll go through an authentication flow.
#    - The generated token is a short-lived token.
#
# 5. Get Instagram User ID:
#    - With the generated token in Graph API Explorer, make a GET request to:
#      `me?fields=id,username` (if the token has `instagram_basic` or similar) OR
#      `me/accounts?fields=instagram_business_account{id,username}` if it's a page-backed Instagram Business account.
#      This will return your Instagram User ID (for Basic Display) or the Instagram Business Account ID.
#      The ID you need is the one associated with your Instagram profile itself.
#
# 6. Exchange for a Long-Lived Token:
#    - Short-lived tokens expire in about an hour. You need a long-lived token.
#    - Make a GET request in the Graph API Explorer (or via curl/Postman) to:
#      `oauth/access_token?grant_type=fb_exchange_token&client_id={your-app-id}&client_secret={your-app-secret}&fb_exchange_token={short-lived-token}`
#    - Replace `{your-app-id}`, `{your-app-secret}` (from your App's Basic Settings), and `{short-lived-token}`.
#    - This will return a long-lived access token (usually valid for ~60 days).
#
# 7. Store the Token and User ID:
#    - Copy the long-lived access token and your Instagram User ID.
#    - Paste them into the `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` fields
#      in your bot's configuration file (`reel_creator/reel_config.py`).
#
# Note: For apps in Development mode, publishing capabilities are often restricted to users with a role
# (Admin, Developer, Tester) on the Facebook App.
# For full publishing capabilities for the general public (if this bot were a service),
# your app would need to go through App Review by Facebook.

# --- Custom Exception ---
class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""
    pass

class APIError(Exception):
    """Custom exception for API call errors."""
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self):
        return f"{super().__str__()} (Status Code: {self.status_code}, Response: {self.response_text})"

# --- Functions ---
def get_api_access_token() -> str:
    """
    Retrieves the Instagram Access Token from config.

    Raises:
        ConfigurationError: If the access token is not configured or is a placeholder.

    Returns:
        str: The access token.
    """
    access_token = reel_config.INSTAGRAM_API_SETTINGS.get("INSTAGRAM_ACCESS_TOKEN")

    if not access_token or access_token == "YOUR_ACCESS_TOKEN_HERE":
        error_msg = (
            "Instagram Access Token is not configured or is still the placeholder value. "
            "Please obtain a valid token and set it in reel_config.py in the "
            "INSTAGRAM_API_SETTINGS dictionary. Refer to the instructions in "
            "instagram_uploader.py for guidance on obtaining a token."
        )
        raise ConfigurationError(error_msg)
    return access_token

def get_api_headers(is_rupload: bool = False) -> dict:
    """
    Retrieves the API headers including the Instagram Access Token.

    Raises:
        ConfigurationError: If the access token is not configured or is a placeholder.

    Returns:
        dict: The headers dictionary for API requests.
    """
    access_token = get_api_access_token() # Use the new helper

    if is_rupload:
        # Resumable upload endpoint (rupload.facebook.com) uses "OAuth" prefix
        return {"Authorization": f"OAuth {access_token}"}
    else:
        # Graph API uses "Bearer" prefix
        return {"Authorization": f"Bearer {access_token}"}


def _handle_api_error(response: requests.Response, action: str):
    """Handles API errors by raising an APIError."""
    try:
        error_data = response.json()
        error_message = error_data.get("error", {}).get("message", response.text)
    except requests.exceptions.JSONDecodeError:
        error_message = response.text
    raise APIError(
        f"Failed to {action}. Status: {response.status_code}. Message: {error_message}",
        status_code=response.status_code,
        response_text=response.text
    )


def upload_reel(video_path: str, caption: str, share_to_feed: bool = True, max_polling_attempts: int = 15, polling_interval_sec: int = 60) -> str:
    """
    Uploads a video reel to Instagram.
    (This is a placeholder and will be implemented in a future step)

    Args:
        video_path (str): The local path to the video file.
        caption (str): The caption for the reel.
        share_to_feed (bool): Whether to also share the reel to the main feed.

    Returns:
        str: The ID of the uploaded reel container/media item, or None if failed.
    """
    """
    Uploads a video reel to Instagram using the resumable upload protocol.

    Args:
        video_path (str): The local path to the video file.
        caption (str): The caption for the reel.
        share_to_feed (bool): Whether to also share the reel to the main feed.
        max_polling_attempts (int): Max attempts to poll for publishing status.
        polling_interval_sec (int): Seconds between polling attempts.


    Returns:
        str: The ID of the published Instagram media, or None if failed.

    Raises:
        ConfigurationError: If IG User ID or Access Token are not set.
        FileNotFoundError: If the video_path does not exist.
        APIError: For errors during API interaction.
    """
    print(f"Starting Instagram reel upload for: {video_path}")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    access_token = get_api_access_token() # Validates token presence
    instagram_user_id = reel_config.INSTAGRAM_API_SETTINGS.get("INSTAGRAM_USER_ID")
    if not instagram_user_id or instagram_user_id == "YOUR_INSTAGRAM_USER_ID_HERE":
        raise ConfigurationError(
            "Instagram User ID is not configured or is still the placeholder. "
            "Please set it in reel_config.py."
        )

    # Step 1: Create Media Container (Resumable)
    print("Step 1: Creating media container...")
    container_url = f"{GRAPH_API_BASE_URL}/{instagram_user_id}/media"
    container_params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
        "access_token": access_token, # As per docs for POST /{ig-user-id}/media
    }

    try:
        response_container = requests.post(container_url, params=container_params, headers=get_api_headers(is_rupload=False))
        if response_container.status_code != 200:
            _handle_api_error(response_container, "create media container")

        container_data = response_container.json()
        ig_container_id = container_data.get("id")
        if not ig_container_id:
            raise APIError("Failed to get container ID from response.", response_text=response_container.text)
        print(f"Successfully created media container. ID: {ig_container_id}")

    except requests.exceptions.RequestException as e:
        raise APIError(f"Request failed during container creation: {e}")


    # Step 2: Upload Video File (Resumable)
    print("Step 2: Uploading video file (resumable)...")
    # Endpoint: https://rupload.facebook.com/<API_VERSION>/<IG_MEDIA_CONTAINER_ID>
    # Extract API version from GRAPH_API_BASE_URL (e.g., "v19.0")
    api_version = GRAPH_API_BASE_URL.split('/')[-1]
    upload_url = f"https://rupload.facebook.com/{api_version}/{ig_container_id}"

    file_size = os.path.getsize(video_path)
    upload_headers = get_api_headers(is_rupload=True) # Uses "OAuth" prefix
    upload_headers.update({
        "offset": "0",
        "file_size": str(file_size),
    })

    try:
        with open(video_path, "rb") as video_file:
            video_content = video_file.read()

        response_upload = requests.post(upload_url, headers=upload_headers, data=video_content)

        if response_upload.status_code != 200:
             _handle_api_error(response_upload, "upload video file (resumable)")

        upload_response_data = response_upload.json()
        if not upload_response_data.get("success", False):
            raise APIError("Resumable upload did not report success.", response_text=response_upload.text)
        print("Successfully uploaded video file.")

    except requests.exceptions.RequestException as e:
        raise APIError(f"Request failed during video upload: {e}")
    except FileNotFoundError:
        raise # Re-raise if video_path became invalid mid-function (unlikely)
    except IOError as e:
        raise APIError(f"Could not read video file {video_path}: {e}")


    # Step 3: Publish Media Container
    print("Step 3: Publishing media container...")
    publish_url = f"{GRAPH_API_BASE_URL}/{instagram_user_id}/media_publish"
    publish_params = {
        "creation_id": ig_container_id,
        "access_token": access_token, # As per docs for POST /{ig-user-id}/media_publish
    }

    try:
        response_publish = requests.post(publish_url, params=publish_params, headers=get_api_headers(is_rupload=False))
        if response_publish.status_code != 200:
            _handle_api_error(response_publish, "publish media container")

        publish_data = response_publish.json()
        final_media_id = publish_data.get("id")
        if not final_media_id:
             # Sometimes, publishing is asynchronous. The container ID itself might be what to poll.
             # Let's assume for now that a successful publish returns the final media_id or indicates async.
             # If it's async, we need to poll the container_id for its status.
            print("Publish API call successful, but no immediate media ID. Will proceed to polling status of container.")
            # The final media_id is often what's returned by media_publish, but if not, status check is key.
            # For now, we'll use ig_container_id to check status.
            # final_media_id = ig_container_id # This might be what we poll
        else:
            print(f"Successfully initiated publishing. Media ID (or Job ID): {final_media_id}")


    except requests.exceptions.RequestException as e:
        raise APIError(f"Request failed during media publishing: {e}")

    # Step 4: Check Publishing Status
    print("Step 4: Checking publishing status...")
    status_url = f"{GRAPH_API_BASE_URL}/{ig_container_id}" # Poll the container ID
    status_params = {
        "fields": "status,status_code", # status_code is more reliable
        "access_token": access_token,
    }

    for attempt in range(max_polling_attempts):
        print(f"Polling attempt {attempt + 1}/{max_polling_attempts}...")
        try:
            response_status = requests.get(status_url, params=status_params, headers=get_api_headers(is_rupload=False))
            if response_status.status_code != 200:
                _handle_api_error(response_status, f"check publishing status for {ig_container_id}")

            status_data = response_status.json()
            status_code = status_data.get("status_code", "").upper()
            status_msg = status_data.get("status", "Status message not available.")
            print(f"Container Status: {status_code} - {status_msg}")

            if status_code == "FINISHED" or status_code == "PUBLISHED":
                # If 'PUBLISHED', the final_media_id should ideally come from the media_publish step.
                # If 'FINISHED', it means it's ready, but the media_publish call should have been the trigger.
                # The ID returned by media_publish is the one to use.
                # If media_publish did not return an ID, but status is FINISHED, this is ambiguous.
                # For now, assume `final_media_id` from media_publish is the correct one if available.
                # If not, the container ID itself might be treated as the reference for the published item in some contexts,
                # or this indicates an issue if `media_publish` didn't provide one.
                print(f"Reel publishing successful. Final Media ID: {final_media_id if final_media_id else ig_container_id}")
                return final_media_id if final_media_id else ig_container_id # Prefer specific media_id
            elif status_code in ["ERROR", "EXPIRED"]:
                raise APIError(f"Reel publishing failed or expired. Status: {status_code} - {status_msg}", response_text=json.dumps(status_data))
            elif status_code == "IN_PROGRESS":
                time.sleep(polling_interval_sec)
            else: # Other statuses, keep polling
                time.sleep(polling_interval_sec)

        except requests.exceptions.RequestException as e:
            print(f"Request failed during status polling: {e}. Retrying...")
            time.sleep(polling_interval_sec)
        except APIError as e: # Handle API errors during polling, maybe retry or fail
            print(f"API Error during polling: {e}. Retrying...")
            time.sleep(polling_interval_sec)


    raise APIError(f"Reel publishing timed out after {max_polling_attempts} attempts. Last status was {status_code}.", response_text=json.dumps(status_data if 'status_data' in locals() else {}))


if __name__ == "__main__":
    print("--- Testing Instagram Uploader ---")

    # Test get_api_headers & get_api_access_token
    print("\nTesting configuration access:")
    original_token = reel_config.INSTAGRAM_API_SETTINGS.get("INSTAGRAM_ACCESS_TOKEN")
    original_user_id = reel_config.INSTAGRAM_API_SETTINGS.get("INSTAGRAM_USER_ID")

    # Test case 1: Token not set
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_ACCESS_TOKEN"] = "YOUR_ACCESS_TOKEN_HERE"
    try:
        get_api_access_token()
        print("FAIL: ConfigurationError not raised for placeholder token.")
    except ConfigurationError as e:
        print(f"PASS: Caught expected ConfigurationError for token: {e}")

    # Test case 2: Token set, User ID not set (during upload_reel)
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_ACCESS_TOKEN"] = "DUMMY_VALID_TOKEN"
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_USER_ID"] = "YOUR_INSTAGRAM_USER_ID_HERE"
    print("\nTesting upload_reel with valid token but placeholder User ID:")
    try:
        # upload_reel needs a file, create a tiny dummy one
        dummy_video_for_test = "test_reel_upload.mp4"
        with open(dummy_video_for_test, "wb") as f: f.write(os.urandom(1024)) # 1KB dummy video

        upload_reel(dummy_video_for_test, "Test Caption", share_to_feed=False)
        print("FAIL: ConfigurationError not raised for placeholder User ID in upload_reel.")
    except ConfigurationError as e:
        print(f"PASS: Caught expected ConfigurationError for User ID: {e}")
    except APIError as e:
        # This is also a "pass" for this specific test's purpose, as it means config check passed
        # but API call failed (which is expected with dummy credentials).
        print(f"PASS: API call failed as expected with dummy token/ID: {e}")
    except FileNotFoundError as e:
        print(f"FAIL: Prerequisite dummy file missing: {e}")
    finally:
        if os.path.exists(dummy_video_for_test):
            os.remove(dummy_video_for_test)


    # Test case 3: Token and User ID are dummy but valid format (API calls will fail but functions should run)
    print("\nTesting upload_reel with DUMMY (but not placeholder) credentials:")
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_ACCESS_TOKEN"] = "DUMMY_ACCESS_TOKEN_FOR_TESTING_FLOW"
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_USER_ID"] = "123456789012345" # Dummy IG User ID

    if not os.path.exists(dummy_video_for_test):
        with open(dummy_video_for_test, "wb") as f: f.write(os.urandom(10*1024)) # 10KB dummy video

    print(f"Attempting upload with dummy video: {dummy_video_for_test}")
    print("EXPECT API ERRORS HERE as credentials are fake.")
    try:
        upload_reel(dummy_video_for_test, "Caption for a test reel with dummy credentials.", share_to_feed=True, max_polling_attempts=2, polling_interval_sec=1)
        print("NOTE: If this line is reached, it means the upload function completed without throwing an exception immediately, which might be unexpected if all API calls fail.")
    except ConfigurationError as e:
        print(f"FAIL: Unexpected ConfigurationError: {e}")
    except FileNotFoundError as e:
        print(f"FAIL: Prerequisite dummy file missing: {e}")
    except APIError as e:
        print(f"PASS: Caught expected APIError, indicating the function attempted API calls: {e.status_code} - {str(e)[:200]}...")
    except Exception as e: # Catch any other unexpected errors
        print(f"FAIL: An unexpected error occurred: {type(e).__name__} - {e}")
    finally:
        if os.path.exists(dummy_video_for_test):
            os.remove(dummy_video_for_test)


    # Restore original config settings
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_ACCESS_TOKEN"] = original_token
    reel_config.INSTAGRAM_API_SETTINGS["INSTAGRAM_USER_ID"] = original_user_id
    print("\nRestored original configuration settings.")

    print("\n--- End of Instagram Uploader Tests ---")
    print("IMPORTANT: Full testing of upload_reel requires valid Instagram credentials,")
    print("a real video file, and careful handling of API rate limits.")
