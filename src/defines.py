import requests
import json
import os


def get_credentials():
    """ gets credentials required for use in the applications

    Returns: dictionary: credentials needed globally
    """

    api_key = os.getenv("API_KEY")
    insta_id = os.getenv("INSTA_ID")
    creds = dict()
    creds['access_token'] = api_key

    creds['graph_domain'] = 'https://graph.facebook.com/'
    creds['graph_version'] = 'v6.0'
    creds['endpoint_base'] = creds['graph_domain'] + creds[
        'graph_version'] + '/'

    creds['instagram_account_id'] = insta_id

    return creds


def make_api_call(url, endpoint_params, request_type):
    """ Request data from endpoint with params

    Args:
        url: string of the url endpoint to make request from
        endpoint_params: dictionary keyed by the names of the url parameters
        request_type: str of request type

    Returns:
        object: data from the endpoint

    """

    if request_type == 'POST':
        data = requests.post(url, endpoint_params)
    else:
        data = requests.get(url, endpoint_params)

    response = dict()
    response['url'] = url

    response['endpoint_params'] = endpoint_params
    response['endpoint_params_pretty'] = json.dumps(endpoint_params, indent=4)

    response['json_data'] = json.loads(data.content)
    response['json_data_pretty'] = json.dumps(response['json_data'], indent=4)

    return response
