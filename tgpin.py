import base64
import os
import re
from datetime import datetime, timedelta
import html2text
import humanize
import json
import pytz

# TODO: better template for the email (logo)
# TODO: add readme + logo
# TODO: publish GH

from telethon import TelegramClient
from telethon.tl.custom import Message
from telethon.tl.types import MessageMediaPhoto, InputMessagesFilterPinned
from telethon.helpers import TotalList

from db.db import Database
from config.config import Config
from emails.emails import send_email

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = Config.instance()

ALERT_NEW = CONFIG.getboolean("alerts", "alert_new")
ALERT_REMINDER = CONFIG.getboolean("alerts", "alert_reminder")
REMINDER_LIMIT = CONFIG.reminder_limit
INCLUDE_CHANNEL = CONFIG.getboolean("alerts", "include_channel")

API_ID = int(CONFIG.api_id)
API_HASH = CONFIG.api_hash
CHANNEL = CONFIG.channel

EMAIL_ADDRESS = CONFIG.email_address
EMAIL_PASSWORD = CONFIG.email_password
EMAIL_HOST = CONFIG.email_host
EMAIL_PORT = CONFIG.email_port
EMAIL_STRINGS_PATH = CONFIG.email_strings_path
EMAIL_TEMPLATE_PATH = CONFIG.email_template_path

DB_PATH = CONFIG.db_path

TIMEZONE = CONFIG.timezone
TIME_FORMAT = CONFIG.time_format
TIME_WINDOW_MINUTES = CONFIG.time_window_minutes

DEBUG = CONFIG.getboolean("debug", "debug")

CONFIG.validate_config()

EMAIL_STRINGS = json.loads(
    open(os.path.join(CURRENT_DIR, EMAIL_STRINGS_PATH), "r").read()
)

TZ = pytz.timezone(TIMEZONE)

# replace "Me" (title used by Telethon) with the actual channel name, "Saved Messages"
CHANNEL_MAP = {
    "Me": "Saved Messages",
}

if DEBUG:
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        filename=os.path.join(CURRENT_DIR, "logs/tgpin.log"),
        filemode="a+",
        format="[%(asctime)-15s] {%(pathname)s:%(lineno)d} "
        "%(levelname)-8s %(message)s",
    )

if not any((ALERT_NEW, ALERT_REMINDER)):
    if DEBUG:
        logging.warning("No alerts enabled!")


TELEGRAM_CLIENT = TelegramClient("anon", API_ID, API_HASH)


def url_to_anchor(url: str) -> str:
    """
    Converts a URL into an HTML anchor tag.

    Args:
        url (str): The URL to convert.

    Returns:
        str: The HTML anchor tag representing the URL.
    """
    return re.sub(r"(https?://[^/]+(?:[^\s]*))", r'<a href="\1">\1</a>', url)


def get_image_src(image_blob: bytes) -> str:
    """
    Retrieves the image source from the image blob.

    Args:
        image_blob (bytes): The image blob.

    Returns:
        str: The image source.
    """
    return f"data:image/png;base64,{base64.b64encode(image_blob).decode("utf-8")}"


def encode_image(image_path: str) -> str:
    """
    Encodes an image to base64.

    Args:
        image_path (str): The path to the image.

    Returns:
        str: The base64-encoded image.
    """
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    return f"data:image/png;base64,{encoded_string}"


def get_email_string(token: str, count: int = 0, include_channel: bool = False) -> str:
    """
    Retrieves an email string based on the provided token.

    Args:
        token (str): The token used to retrieve the email string.
        count (int): The count value used in the email string formatting.
        include_channel (bool): Whether to include the channel name in the email string.

    Returns:
        str: The email string based on the provided parameters.
    """
    if include_channel:
        token += "_channel"
    if count == 1:
        token += "_sg"
    return EMAIL_STRINGS[token]


def humanize_time_diff(d1: datetime, d2: datetime) -> str:
    """
    Returns a humanized string representing the time difference between two dates.

    Args:
        d1 (datetime): The first date.
        d2 (datetime): The second date.

    Returns:
        str: The humanized string representing the time difference between the two dates.
    """
    return humanize.naturaltime(d1 - d2)


def send_email_with_html(
    subject: str, count: int, html: str, plain_text: str
):
    """
    Sends an email with HTML content.

    Args:
        subject (str): The subject of the email.
        count (int): The count value used in the subject formatting.
        html (str): The HTML content of the email.
        plain_text (str): The plain text content of the email.
    """
    send_email(
        EMAIL_ADDRESS,
        EMAIL_PASSWORD,
        EMAIL_HOST,
        EMAIL_PORT,
        subject.format(c=count),
        html,
        plain_text,
    )


def generate_html_content(messages: list, count: int, total_count: int,
                          time_window: datetime, _type: str = "") -> str:
    """
    Generates HTML content for an email template using the provided messages.

    Args:
        messages (list): A list of messages,
        where each message is a tuple containing the message details.
        count (int): The count value used in the HTML content formatting.
        total_count (int): The total count of messages used in the
        HTML content formatting.
        time_window (datetime): The time window used in the HTML content formatting.
        _type (str): The type of email alert (new or reminder),
        used to retrieve the email strings.

    Returns:
        str: The generated HTML content for the email template.
    """
    with open(
        os.path.join(CURRENT_DIR, EMAIL_TEMPLATE_PATH), "r", encoding="utf8"
    ) as f:
        return f.read().format(
            logo=encode_image(os.path.join(CURRENT_DIR, "assets/logo.png")),
            title=get_email_string("title_" + _type),
            intro_msg=get_email_string("intro_msg_" + _type, count, INCLUDE_CHANNEL)
            .format(c=count,
                    total_msg=get_email_string("total", total_count)
                    .format(t=total_count),
                    d=time_window.strftime(TIME_FORMAT),
                    ch=CHANNEL_MAP.get(CHANNEL.title(), "Unknown Channel Mapping")
                    if INCLUDE_CHANNEL else ""),
            table="".join(
                f"""
                <tr>
                <td style="padding: 10px;">{m[0]}</td>
                <td style="padding: 10px;">{m[1]}<br>
                {f"<img src='{get_image_src(m[3])}' \
                 style='max-width: 300px; height: auto;' />" if m[3] else ""}</td>
                <td style="padding: 10px;">{datetime.fromisoformat(m[2])
                                            .strftime(TIME_FORMAT)}
                <br>(<b>{humanize_time_diff
                         (
                          datetime.now(TZ),
                          datetime.fromisoformat(m[2])
                          .replace(tzinfo=pytz.timezone(TIMEZONE)),
                         )}</b>)</td>
                </tr>
                """
                for m in messages
            )
        )


async def get_image_data(message: Message) -> bytes | None:
    """
    Retrieves the image data from a given message.

    Args:
        message (Message): The message containing the image.

    Returns:
        bytes: The image data.
    """
    if isinstance(message.media, MessageMediaPhoto):
        return await message.download_media(bytes)
    return None


async def get_pinned_messages(client: TelegramClient, channel: str) -> TotalList | list:
    """
    Retrieves the pinned messages from a given channel.

    Args:
        client (TelegramClient): The Telegram client instance.
        channel (str): The channel where the pinned messages are located.

    Returns:
        TotalList | list: The pinned messages from the channel.
    """
    pinned_messages = await client.get_messages(
        channel, filter=InputMessagesFilterPinned(), limit=1000
    )

    if pinned_messages is None:
        if DEBUG:
            logging.warning("No pinned messages found in %s", channel)
        return []
    if isinstance(pinned_messages, list):
        if DEBUG:
            logging.info(
                "Found %d pinned messages in %s", len(pinned_messages), channel
            )
        return pinned_messages
    return [pinned_messages]


async def main():
    db_instance = Database(CONFIG.get_base_dir(), DB_PATH)
    table_exists = db_instance.table_exists("pinned_messages")
    if not table_exists:
        if DEBUG:
            logging.info("Creating table")
        db_instance.create_table()

    pinned_messages = await get_pinned_messages(TELEGRAM_CLIENT, CHANNEL)
    total_count = len(pinned_messages)

    pin_data = [(
        m.id,
        m.text,
        m.date.replace(tzinfo=pytz.utc).astimezone(TZ),
        await get_image_data(m))
        for m in pinned_messages
    ]

    db_instance.insert_or_ignore(pin_data, DEBUG)

    time_window = datetime.now(TZ) - timedelta(minutes=TIME_WINDOW_MINUTES)
    recent_messages = db_instance.get_recent_messages(time_window)
    recent_count = len(recent_messages)

    if ALERT_NEW and recent_count > 0:
        recent_messages = [
            (m[0], url_to_anchor(m[1]), m[2], m[3]) for m in recent_messages
        ]
        html = generate_html_content(recent_messages, recent_count, total_count,
                                     time_window, "new")
        plain_text = html2text.html2text(html)

        send_email_with_html(
            get_email_string("subject_new", recent_count),
            recent_count,
            html,
            plain_text,
        )

    reminder_messages = db_instance.get_random_messages(REMINDER_LIMIT)
    reminder_count = len(reminder_messages)

    if ALERT_REMINDER and reminder_count > 0:
        reminder_messages = [
            (m[0], url_to_anchor(m[1]), m[2], m[3]) for m in reminder_messages
        ]
        html = generate_html_content(reminder_messages, reminder_count, total_count,
                                     time_window, "reminder")
        plain_text = html2text.html2text(html)

        send_email_with_html(
            get_email_string("subject_reminder", reminder_count),
            reminder_count,
            html,
            plain_text,
        )

    db_instance.close()


with TELEGRAM_CLIENT:
    TELEGRAM_CLIENT.loop.run_until_complete(main())
