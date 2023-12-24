import os
import requests
from heroku3 import from_key

def get_new_token(app_id, app_secret, access_token):
    """Get a new token using the old token."""
    url = f"https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': app_id,
        'client_secret': app_secret,
        'fb_exchange_token': access_token,
    }
    response = requests.get(url, params=params)
    return response.json()

def update_heroku_config_var(app_name, var_name, new_value):
    """Update a Heroku config var."""
    heroku_conn = from_key(os.getenv('HEROKU_API_KEY'))
    app = heroku_conn.apps()[app_name]
    app.config()[var_name] = new_value

def update_token():
    """Main function to update the Graph API token."""
    new_token_info = get_new_token(
        os.getenv('FB_APP_ID'),
        os.getenv('FB_APP_SECRET'),
        os.getenv('ACCESS_TOKEN')
    )
    update_heroku_config_var('crossposter', 'ACCESS_TOKEN', new_token_info['access_token'])


if __name__ == "__main__":
    update_token()
