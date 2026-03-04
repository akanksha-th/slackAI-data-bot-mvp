from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.core.config import get_settings
from src.core.logging import get_logger
from typing import Any
import io

logger = get_logger(__name__)
settings = get_settings()

client = WebClient(token=settings.SLACK_BOT_TOKEN)

def post_message(channel: str, blocks: list[dict], text: str = 'Query result') -> None:
    try:
        client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=text
        )
    except SlackApiError as e:
        logger.error()
        raise

def post_ephermeral_ack(response_url: str, text: str) -> None:
    """Post immediate acknowledgement via response_url (no SDK needed)."""
    import httpx
    httpx.post(response_url, json={
        "response_type": "ephemeral",
        "text": text
    })

def upload_csv(channel: str, file: io.BytesIO, filename: str, title: str) -> None:
    try:
        client.files_upload_v2(
            channel=channel,
            file=file,
            filename=filename,
            title=title
        )
        logger.info(f"CSV uploaded to channel {channel}")
    except SlackApiError as e:
        logger.error(f"Failed to upload CSV: {e.response['error']}")
        raise