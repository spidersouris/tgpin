import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(address, password, host, port, subject, html_content, plain_text):
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
        print(f"Error sending email: {e}")
