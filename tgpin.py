"""
Script to retrieve pinned messages from a Telegram channel, store them in a database,
and send email alerts for new and reminder messages.
"""

import base64
import os
from datetime import datetime, timedelta
import html2text
import humanize
import json
import logging
import pytz
import re

from telethon import TelegramClient
from telethon.tl.custom import Message
from telethon.tl.types import MessageMediaPhoto, InputMessagesFilterPinned
from telethon.helpers import TotalList

from db.db import Database
from config.config import load_config, validate_config, get_base_dir
from emails.emails import send_email

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = load_config()

# [alerts]
ALERT_NEW = CONFIG.getboolean("alerts", "alert_new")
ALERT_NEW_TIME_WINDOW_MINUTES = int(CONFIG.alerts.alert_new_time_window_minutes)

ALERT_REMINDER = CONFIG.getboolean("alerts", "alert_reminder")
REMINDER_LIMIT = CONFIG.alerts.alert_reminder_limit
INCLUDE_CHANNEL = CONFIG.getboolean("alerts", "include_channel")

# [telegram]
API_ID = CONFIG.telegram.api_id
API_HASH = CONFIG.telegram.api_hash
CHANNEL = CONFIG.telegram.channel

# [email]
EMAIL_ADDRESS = CONFIG.email.address
EMAIL_PASSWORD = CONFIG.email.password
EMAIL_HOST = CONFIG.email.host
EMAIL_PORT = CONFIG.email.port
EMAIL_STRINGS_PATH = CONFIG.email.email_strings_path
EMAIL_TEMPLATE_PATH = CONFIG.email.email_template_path

# [database]
DB_PATH = CONFIG.database.db_path

# [time]
TIMEZONE = CONFIG.time.timezone
TIME_FORMAT = CONFIG.time.time_format

# [debug]
LOG_LEVEL = CONFIG.debug.log_level
LOG_CHILDREN = CONFIG.getboolean("debug", "log_children")
SAVE_LOGS_TO_FILE = CONFIG.getboolean("debug", "save_logs_to_file")
LOG_PATH = CONFIG.debug.log_path

validate_config(CONFIG)

EMAIL_STRINGS = json.loads(
    open(os.path.join(CURRENT_DIR, EMAIL_STRINGS_PATH), "r").read()
)

TZ = pytz.timezone(TIMEZONE)

# replace "Me" (title used by Telethon) with the actual channel name, "Saved Messages"
CHANNEL_MAP = {
    "Me": "Saved Messages",
}

# set up logging
logfmt = logging.Formatter(
    "[%(asctime)-15s] {%(pathname)s:%(lineno)d} " "%(levelname)-4s %(message)s"
)

if LOG_CHILDREN:
    logger = logging.getLogger()
else:
    logger = logging.getLogger(__name__)

logger.setLevel(LOG_LEVEL)

if SAVE_LOGS_TO_FILE:
    fh = logging.FileHandler(LOG_PATH)
    fh.setLevel(LOG_LEVEL)
    fh.setFormatter(logfmt)
    logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
ch.setFormatter(logfmt)
logger.addHandler(ch)

logger.debug(
    f"""Launching script with the following configuration
    from {CONFIG.get_config_path()}:\n\n{CONFIG.list_config_values()}"""
)

if not any((ALERT_NEW, ALERT_REMINDER)):
    logger.warning("No alerts enabled! No emails will be sent.")

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
    return f'data:image/png;base64,{base64.b64encode(image_blob).decode("utf-8")}'


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


def setup_database() -> tuple[Database, bool, bool]:
    """
    Sets up the database by creating a table if it doesn't exist.
    Returns the database instance, along with alert settings for new messages.

    Returns:
        tuple[Database, bool, bool]: A tuple containing the database instance,
        and the alert settings for new messages (both by time window and last update).
    """
    db_instance = Database(get_base_dir(), DB_PATH)
    table_exists = db_instance.table_exists("pinned_messages")

    alert_new_get_by_last_update = CONFIG.getboolean(
        "alerts", "alert_new_get_by_last_update"
    )
    alert_new_get_by_time_window = CONFIG.getboolean(
        "alerts", "alert_new_get_by_time_window"
    )

    if not table_exists:
        if alert_new_get_by_last_update:
            logger.warn(
                """get_by_last_update cannot be used without a table\n
                Forcing get_by_time_window"""
            )
            alert_new_get_by_last_update = False
            alert_new_get_by_time_window = True
        logger.info("Table does not exist; creating...")
        db_instance.create_table()

    return db_instance, alert_new_get_by_time_window, alert_new_get_by_last_update


async def process_pinned_messages(
    telegram_client: TelegramClient, channel: str
) -> tuple[list[tuple[int, str, datetime, bytes | None]], int]:
    """
    Processes the pinned messages of a Telegram channel.

    Args:
        telegram_client (TelegramClient): The Telegram client object.
        channel (str): The channel name or ID.

    Returns:
        tuple: A tuple containing the processed pinned messages data
        (i.e. message ID, message text, message date, and image data),
        and the total count of pinned messages.
    """
    pinned_messages = await get_pinned_messages(telegram_client, channel)
    total_count = len(pinned_messages)
    pin_data = sorted(
        [
            (
                m.id,
                m.text,
                m.date.replace(tzinfo=pytz.utc).astimezone(TZ),
                await get_image_data(m),
            )
            for m in pinned_messages
        ],
        key=lambda x: x[0],
    )
    return pin_data, total_count


def update_database(
    db_instance: Database,
    pin_data: list[tuple[int, str, datetime, bytes | None]],
    alert_new_get_by_last_update: bool,
) -> str | None:
    """
    Updates the database with the given pin data.

    Args:
        db_instance (Database): The instance of the database.
        pin_data (list[tuple[int, str, datetime, bytes | None]): The list of
        pin messages data that needs to be updated.
        alert_new_get_by_last_update (bool): Flag indicating whether to alert
        for new pins.

    Returns:
        str | None: The last update time if alerting by last update, otherwise None.
    """
    messages_ids = [m[0] for m in pin_data]
    db_instance.remove_unpinned_messages(messages_ids)
    last_update = db_instance.insert_or_ignore(pin_data, alert_new_get_by_last_update)
    return last_update


def get_recent_messages(
    db_instance: Database,
    alert_new_get_by_time_window: bool,
    alert_new_get_by_last_update: bool,
    last_update: str | None,
) -> tuple[list[tuple], datetime]:
    """
    Retrieves the recent messages from the database based on the specified criteria.

    Args:
        db_instance (Database): The instance of the database to retrieve messages from.
        alert_new_get_by_time_window (bool): Flag indicating whether to retrieve messages
        within a time window.
        alert_new_get_by_last_update (bool): Flag indicating whether to retrieve messages
        based on the last update time.
        last_update (str | None): The last update time to retrieve messages from.

    Returns:
        Tuple[List[Message], datetime]: A tuple containing the list of retrieved messages
        (if any) and the time window used for retrieval.
    """
    time_window = datetime.now(TZ) - timedelta(minutes=ALERT_NEW_TIME_WINDOW_MINUTES)
    if alert_new_get_by_time_window:
        return db_instance.get_recent_messages_by_date(time_window), time_window
    elif alert_new_get_by_last_update and last_update:
        return db_instance.get_recent_messages_by_date(last_update), time_window
    return [], time_window


def process_alerts(
    messages: list, total_count: int, time_window: datetime, alert_type: str
) -> None:
    """
    Processes alerts based on the messages.

    Args:
        messages (list): List of messages.
        total_count (int): Total count of messages.
        time_window (datetime): Time window for the alerts.
        alert_type (str): Type of alert.
    """
    count = len(messages)
    if count > 0:
        messages = [(m[1], url_to_anchor(m[2]), m[3], m[4]) for m in messages]
        html = generate_html_content(
            messages, count, total_count, time_window, alert_type
        )
        plain_text = html2text.html2text(html)
        send_email_with_html(
            get_email_string(f"subject_{alert_type}", count),
            count,
            html,
            plain_text,
        )


def send_email_with_html(subject: str, count: int, html: str, plain_text: str) -> None:
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


def generate_html_content(
    messages: list, count: int, total_count: int, time_window: datetime, _type: str = ""
) -> str:
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
            intro_msg=get_email_string(
                "intro_msg_" + _type, count, INCLUDE_CHANNEL
            ).format(
                c=count,
                total_msg=get_email_string("total", total_count).format(t=total_count),
                d=time_window.strftime(TIME_FORMAT),
                ch=(
                    CHANNEL_MAP.get(CHANNEL.title(), "Unknown Channel Mapping")
                    if INCLUDE_CHANNEL
                    else ""
                ),
            ),
            table="".join(
                f"""
                <tr>
                <td style="padding: 10px;">{m[0]}</td>
                <td style="padding: 10px;">{m[1]}<br>
                {f"<img src='{get_image_src(m[3])}'style='max-width:300px;height:auto;'/>"
                 if m[3] else ""}</td>
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
            ),
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
        logger.warning("No pinned messages found in %s", channel)
        return []
    if isinstance(pinned_messages, list):
        logger.info("Found %d pinned messages in %s", len(pinned_messages), channel)
        return pinned_messages
    return [pinned_messages]


async def main():
    db_instance, alert_new_get_by_time_window, alert_new_get_by_last_update = (
        setup_database()
    )

    pin_data, total_count = await process_pinned_messages(TELEGRAM_CLIENT, CHANNEL)

    last_update = update_database(db_instance, pin_data, alert_new_get_by_last_update)

    recent_messages, time_window = get_recent_messages(
        db_instance,
        alert_new_get_by_time_window,
        alert_new_get_by_last_update,
        last_update,
    )

    if ALERT_NEW:
        process_alerts(recent_messages, total_count, time_window, "new")

    if ALERT_REMINDER:
        reminder_messages = db_instance.get_random_messages(REMINDER_LIMIT)
        process_alerts(reminder_messages, total_count, time_window, "reminder")

    db_instance.close()


with TELEGRAM_CLIENT:
    TELEGRAM_CLIENT.loop.run_until_complete(main())
