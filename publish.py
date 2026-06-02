from meme_bot.config import BotConfig
from meme_bot.instagram import InstagramClient


def post(url: str, caption: str) -> str:
    """Publish one image post to Instagram and return the media id."""
    config = BotConfig.from_env()
    return InstagramClient(config).post_image(url, caption)
