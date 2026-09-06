"""Transactional email service using Resend."""

import logging
import os
from html import escape
from urllib.parse import quote

import resend

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


async def send_password_reset_email(
    email: str,
    reset_token: str,
) -> None:
    """
    Send password reset email through Resend.
    """

    api_key = settings.resend_api_key.strip()
    sender = settings.email_from.strip()
    recipient = email.strip().lower()

    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not configured"
        )

    if not sender:
        raise RuntimeError(
            "EMAIL_FROM is not configured"
        )

    if not recipient:
        raise ValueError(
            "Recipient email must not be empty"
        )

    if not reset_token:
        raise ValueError(
            "Reset token must not be empty"
        )

    resend.api_key = api_key

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

    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient],
        "subject": "Восстановление пароля — Green Garden",
        "html": html,
    }

    try:
        result = await resend.Emails.send_async(
            params
        )

        email_id = getattr(
            result,
            "id",
            None,
        )

        logger.info(
            "Password reset email sent successfully. "
            "recipient=%s email_id=%s",
            recipient,
            email_id,
        )

    except Exception:
        logger.exception(
            "Failed to send password reset email. "
            "recipient=%s",
            recipient,
        )
        raise
