from typing import Dict
from defines import get_credentials, make_api_call

def create_media_object(parameters: Dict) -> Dict:
    """
    Create media object

    Args:
        parameters: dictionary of params

    Returns:
        object: data from the endpoint
    """
    url = f"{parameters['endpoint_base']}{parameters['instagram_account_id']}/media"

    endpoint_params = {key: parameters[key] for key in ['caption', 'access_token']}

    if 'IMAGE' == parameters['media_type']:
        endpoint_params['image_url'] = parameters['media_url']
    else:
        endpoint_params['media_type'] = parameters['media_type']
        endpoint_params['video_url'] = parameters['media_url']

    return make_api_call(url, endpoint_params, 'POST')


def publish_media(media_object_id: str, parameters: Dict) -> Dict:
    """
    Publish a media object

    Args:
        media_object_id: id of the media object
        parameters: dictionary of params

    Returns:
        object: data from the endpoint
    """
    url = f"{parameters['endpoint_base']}{parameters['instagram_account_id']}/media_publish"
    post_parameters = {
        'creation_id': media_object_id,
        'access_token': parameters['access_token']
    }

    return make_api_call(url, post_parameters, 'POST')


def post(url: str, caption: str) -> None:
    """
    Post content to Instagram

    Args:
        url: URL of the content to post
        caption: Caption for the post
    """
    parameters = get_credentials()
    post_parameters = {
        'image_url': url,
        'caption': caption,
        'access_token': parameters['access_token']
    }

    try:
        # Create the media object
        media_object = make_api_call(parameters['endpoint_base'] + parameters['instagram_account_id'] + '/media', post_parameters, 'POST')
        media_object_id = media_object['json_data']['id']
        print(f"Media Object Created: {media_object_id}")

        parameters['media_object_id'] = media_object_id

        # Publish the media object
        publish_response = publish_media(media_object_id, parameters)
        print(f"Media Object Published: {publish_response}")

    except Exception as e:
        print(f"Error posting content: {e}")
