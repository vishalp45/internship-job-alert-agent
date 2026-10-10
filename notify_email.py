"""Sends the daily digest by Gmail SMTP. Test it: python notify_email.py"""
import os, smtplib, ssl
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
    load_dotenv()          # reads .env locally; on GitHub Actions secrets come from env
except ImportError:
    pass


def _credentials():
    sender = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = os.environ.get("EMAIL_TO", "").strip() or sender
    if not sender or not password:
        raise RuntimeError("EMAIL_ADDRESS or EMAIL_APP_PASSWORD is empty - check the GitHub secrets")
    return sender, password, to


def send_email(subject: str, body_text: str, body_html: str | None = None) -> None:
    sender, password, to = _credentials()

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    ctx = ssl.create_default_context()
    try:                                        # first choice: SSL on port 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as s:
            s.login(sender, password)
            s.send_message(msg)
    except (smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError):
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:   # fallback: STARTTLS on 587
            s.starttls(context=ctx)
            s.login(sender, password)
            s.send_message(msg)


if __name__ == "__main__":
    send_email("Job Agent test", "If you can read this, email alerts work.")
    print("Sent.")
