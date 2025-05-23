import os
import requests
from heroku3 import from_key
import logging
import sys

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_new_token(app_id, app_secret, access_token):
    """Get a new token using the old token."""
    url = f"https://graph.facebook.com/v22.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': access_token,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during requests.get: {e}")
        return None
    
    if response.status_code != 200:
        logging.error(f"Failed to get new token. Status code: {response.status_code}, Response: {response.text}")
        return None

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError as e:
        logging.error(f"Error decoding JSON response: {e}")
        return None

    if 'error' in data:
        logging.error(f"API error: {data['error']}")
        return None

    if 'access_token' not in data:
        logging.error("'access_token' not in response.")
        return None
        
    return data

def update_heroku_config_var(app_name, var_name, new_value):
    """Update a Heroku config var."""
    heroku_api_key = os.getenv('HEROKU_API_KEY')
    if not heroku_api_key:
        logging.error("HEROKU_API_KEY environment variable not set.")
        return False
    try:
        heroku_conn = from_key(heroku_api_key)
        app = heroku_conn.app(app_name) # Changed from apps()[app_name] for direct access and better error handling
        app.config()[var_name] = new_value
        logging.info(f"Successfully updated Heroku config var {var_name} for app {app_name}.")
        return True
    except Exception as e: # Catching a general exception as heroku3 specific exceptions are not well documented
        logging.error(f"Error updating Heroku config var: {e}")
        return False

def update_token():
    """Main function to update the Graph API token."""
    try:
        fb_app_id = os.getenv('FB_APP_ID')
        fb_app_secret = os.getenv('FB_APP_SECRET')
        access_token = os.getenv('ACCESS_TOKEN')
        heroku_app_name = os.getenv('HEROKU_APP_NAME')

        if not all([fb_app_id, fb_app_secret, access_token]):
            logging.error("Facebook App ID, Secret, or Access Token environment variables are missing.")
            sys.exit(1)
        
        if not heroku_app_name:
            logging.error("HEROKU_APP_NAME environment variable not set.")
            sys.exit(1)

        new_token_info = get_new_token(
            fb_app_id,
            fb_app_secret,
            access_token
        )

        if not new_token_info or 'access_token' not in new_token_info:
            logging.error("Failed to obtain new token. Exiting.")
            sys.exit(1)
        
        success = update_heroku_config_var(heroku_app_name, 'ACCESS_TOKEN', new_token_info['access_token'])
        if not success:
            logging.error(f"Failed to update Heroku config variable for app {heroku_app_name}. Exiting.")
            sys.exit(1)
        
        logging.info("Token update process completed successfully.")

    except Exception as e:
        logging.error(f"An unexpected error occurred during the token update process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    update_token()
