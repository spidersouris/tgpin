"""
Module used to send emails.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(
    address: str,
    password: str,
    host: str,
    port: int,
    subject: str,
    html_content: str,
    plain_text: str,
) -> None:
    """
    Sends an email to the specified address with the specified content.

    Args:
        address (str): The email address to send the email to.
        password (str): The password for the email address.
        host (str): The SMTP server host.
        port (int): The SMTP server port.
        subject (str): The subject of the email.
        html_content (str): The HTML content of the email.
        plain_text (str): The plain text content of the email.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = address
        msg["To"] = address
        msg["Subject"] = subject

        text_part = MIMEText(plain_text, "plain/markdown")
        msg.attach(text_part)

        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        server = smtplib.SMTP_SSL(host, port)
        server.login(address, password)
        server.sendmail(address, address, msg.as_string())
        server.quit()
    except Exception as e:
        raise e
