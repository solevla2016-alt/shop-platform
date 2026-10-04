"""Transactional email service using Yandex SMTP."""

import asyncio
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from html import escape
from urllib.parse import quote

from app.core.config import settings


logger = logging.getLogger(__name__)


TEMPLATES_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "templates",
    )
)


def _load_template(
    template_name: str,
) -> str:
    """Read an HTML email template from disk."""
    path = os.path.join(
        TEMPLATES_DIR,
        template_name,
    )

    with open(
        path,
        encoding="utf-8",
    ) as template_file:
        return template_file.read()


def build_password_reset_email(
    reset_url: str,
) -> str:
    """
    Build password reset email HTML from a template file.
    """

    safe_url = escape(
        reset_url,
        quote=True,
    )

    expire_minutes = settings.password_reset_expire_minutes

    template = _load_template(
        "password_reset.html"
    )

    return template.format(
        safe_url=safe_url,
        expire_minutes=expire_minutes,
    )


def _validate_config() -> None:
    if not settings.smtp_user.strip():
        raise RuntimeError("SMTP_USER is not configured")

    if not settings.smtp_password.strip():
        raise RuntimeError("SMTP_PASSWORD is not configured")

    if not settings.smtp_host.strip():
        raise RuntimeError("SMTP_HOST is not configured")

    if not settings.email_from.strip():
        raise RuntimeError("EMAIL_FROM is not configured")


def _send_sync(
    recipient: str,
    subject: str,
    html: str,
) -> None:
    """Send an email through SMTP (blocking call, used with to_thread)."""

    user = settings.smtp_user.strip()
    password = settings.smtp_password.strip()
    host = settings.smtp_host.strip()
    port = settings.smtp_port

    sender = settings.email_from.strip()
    sender_name, sender_addr = _parse_sender(sender)

    message = MIMEMultipart("alternative")
    message["From"] = formataddr(
        (sender_name, sender_addr)
    )
    message["To"] = recipient
    message["Subject"] = subject
    message["X-Mailer"] = "Tierra Shop"

    message.attach(
        MIMEText(
            html,
            "html",
            "utf-8",
        )
    )

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        host,
        port,
        context=context,
        timeout=30,
    ) as server:
        server.login(
            user,
            password,
        )
        server.sendmail(
            sender_addr,
            [recipient],
            message.as_string(),
        )


def _parse_sender(
    sender: str,
) -> tuple[str, str]:
    """Split 'Name <email>' into display name and email address."""
    if "<" in sender and sender.endswith(">"):
        name, email = sender.split("<", maxsplit=1)
        return name.strip(' "'), email.rstrip(">").strip()
    return "", sender.strip()


async def send_password_reset_email(
    email: str,
    reset_token: str,
) -> None:
    """
    Send password reset email through Yandex SMTP.
    """

    _validate_config()

    recipient = email.strip().lower()

    if not recipient:
        raise ValueError(
            "Recipient email must not be empty"
        )

    if not reset_token:
        raise ValueError(
            "Reset token must not be empty"
        )

    encoded_token = quote(
        reset_token,
        safe="",
    )

    frontend_url = settings.frontend_url.rstrip("/")

    reset_url = (
        f"{frontend_url}"
        f"/reset-password"
        f"?token={encoded_token}"
    )

    html = build_password_reset_email(
        reset_url
    )

    subject = "Восстановление пароля — Тьерра"

    try:
        await asyncio.to_thread(
            _send_sync,
            recipient,
            subject,
            html,
        )

        logger.info(
            "Password reset email sent successfully. "
            "recipient=%s",
            recipient,
        )

    except Exception:
        logger.exception(
            "Failed to send password reset email. "
            "recipient=%s",
            recipient,
        )
        raise
