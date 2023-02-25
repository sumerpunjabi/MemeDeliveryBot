import time
from defines import get_credentials, make_api_call


def create_media_object(parameters):
    """ Create media object

    Args:
        parameters: dictionary of params

    API Endpoint:
        https://graph.facebook.com/v5.0/{ig-user-id}/media?image_url={image-url}&caption={caption}&access_token={access-token}
        https://graph.facebook.com/v5.0/{ig-user-id}/media?video_url={video-url}&caption={caption}&access_token={access-token}

    Returns:
        object: data from the endpoint

    """

    url = parameters['endpoint_base'] + parameters[
        'instagram_account_id'] + '/media'

    endpoint_params = dict()
    endpoint_params['caption'] = parameters['caption']
    endpoint_params['access_token'] = parameters['access_token']

    if 'IMAGE' == parameters['media_type']:
        endpoint_params['image_url'] = parameters['media_url']

    else:
        endpoint_params['media_type'] = parameters['media_type']
        endpoint_params['video_url'] = parameters['media_url']

    return make_api_call(url, endpoint_params, 'POST')


def get_media_object_status(media_object_id, parameters):
    """ Check the status of a media object

    Args:
        media_object_id: id of the media object
        parameters: dictionary of params

    API Endpoint:
        https://graph.facebook.com/v5.0/{ig-container-id}?fields=status_code

    Returns:
        object: data from the endpoint

    """

    url = parameters['endpoint_base'] + '/' + media_object_id

    endpoint_params = dict()
    endpoint_params['fields'] = 'status_code'
    endpoint_params['access_token'] = parameters['access_token']

    return make_api_call(url, endpoint_params, 'GET')


def publish_media(media_object_id, parameters):
    """ Publish content

    Args:
        media_object_id: id of the media object
        parameters: dictionary of params

    API Endpoint:
        https://graph.facebook.com/v5.0/{ig-user-id}/media_publish?creation_id={creation-id}&access_token={access-token}

    Returns:
        object: data from the endpoint

    """

    url = parameters['endpoint_base'] + parameters[
        'instagram_account_id'] + '/media_publish'

    endpoint_params = dict()
    endpoint_params['creation_id'] = media_object_id
    endpoint_params['access_token'] = parameters['access_token']

    return make_api_call(url, endpoint_params, 'POST')


def get_content_publishing_limit(parameters):
    """ Get the api limit for the user

    Args:
        parameters: dictionary of params

    API Endpoint:
        https://graph.facebook.com/v5.0/{ig-user-id}/content_publishing_limit?fields=config,quota_usage

    Returns:
        object: data from the endpoint

    """

    url = parameters['endpoint_base'] + parameters[
        'instagram_account_id'] + '/content_publishing_limit'

    endpoint_params = dict()
    endpoint_params['fields'] = 'config,quota_usage'
    endpoint_params['access_token'] = parameters['access_token']

    return make_api_call(url, endpoint_params, 'GET')


def post(url, caption):
    params = get_credentials()

    params['media_type'] = 'IMAGE'
    params['media_url'] = url
    params['caption'] = caption + "\n." + "\n." + "\n#memes #funny"

    image_media_object_response = create_media_object(params)
    image_media_object_id = image_media_object_response['json_data']['id']
    image_media_status_code = 'IN_PROGRESS'

    print("\tID:")
    print("\t" + image_media_object_id)

    while image_media_status_code != 'FINISHED':

        image_media_object_status_response = get_media_object_status(
            image_media_object_id, params)
        image_media_status_code = \
            image_media_object_status_response['json_data']['status_code']

        print("\tStatus Code:")
        print("\t" + image_media_status_code)
        time.sleep(5)

    publish_image_response = publish_media(image_media_object_id, params)
    print(publish_image_response['json_data_pretty'])

    content_publishing_api_limit = get_content_publishing_limit(params)
    print(content_publishing_api_limit['json_data_pretty'])
