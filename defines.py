import requests
import json
import os
from typing import Dict, Union

def get_credentials() -> Dict[str, str]:
    creds = {
        'access_token': os.getenv('ACCESS_TOKEN'),
        'graph_domain': 'https://graph.facebook.com/',
        'graph_version': 'v22.0',
        'instagram_account_id': os.getenv('INSTAGRAM_ACCOUNT_ID'),
    }
    creds['endpoint_base'] = f"{creds['graph_domain']}{creds['graph_version']}/"

    return creds


def make_api_call(url: str, endpoint_params: Dict, request_type: str) -> Dict[str, Union[str, Dict]]:
    """Requests data from endpoint with params.

    Args:
        url: String of the url endpoint to make request from.
        endpoint_params: Dictionary keyed by the names of the url parameters.
        request_type: String of request type.

    Returns:
        dict: Data from the endpoint.

    Raises:
        Exception: If the API response contains an error.
    """
    data = requests.post(url, endpoint_params) if request_type == 'POST' else requests.get(url, endpoint_params)
    json_data = json.loads(data.content)

    if 'error' in json_data:
        print(json_data)
        raise Exception(json_data['error'])

    response = {
        'url': url,
        'endpoint_params': endpoint_params,
        'endpoint_params_pretty': json.dumps(endpoint_params, indent=4),
        'json_data': json_data,
        'json_data_pretty': json.dumps(json_data, indent=4)
    }

    return response