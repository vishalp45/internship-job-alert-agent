"""Sends the daily digest by Gmail SMTP. Test it: python notify_email.py"""
import os, smtplib, ssl
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
    load_dotenv()          # reads .env locally; on GitHub Actions secrets come from env
except ImportError:
    pass

def send_email(subject: str, body_text: str, body_html: str | None = None) -> None:
    sender = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_APP_PASSWORD"]   # Gmail App Password, not your login password
    to = os.environ.get("EMAIL_TO", sender)

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password)
        s.send_message(msg)

if __name__ == "__main__":
    send_email("Job Agent test", "If you can read this, email alerts work.")
    print("Sent.")
