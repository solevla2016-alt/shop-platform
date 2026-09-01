"""Transactional email service using Resend."""

import logging
from html import escape
from urllib.parse import quote

import resend

from app.core.config import settings


logger = logging.getLogger(__name__)


def build_password_reset_email(
    reset_url: str,
) -> str:
    """
    Build password reset email HTML.
    """

    safe_url = escape(
        reset_url,
        quote=True,
    )

    expire_minutes = settings.password_reset_expire_minutes

    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>Восстановление пароля — Green Garden</title>
</head>

<body style="
    margin: 0;
    padding: 0;
    background-color: #f5f7f5;
    font-family: Arial, Helvetica, sans-serif;
">

<table
    width="100%"
    cellpadding="0"
    cellspacing="0"
    role="presentation"
    style="
        background-color: #f5f7f5;
        padding: 40px 20px;
    "
>
    <tr>
        <td align="center">

            <table
                width="100%"
                cellpadding="0"
                cellspacing="0"
                role="presentation"
                style="
                    max-width: 600px;
                    background: #ffffff;
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow:
                        0 4px 20px
                        rgba(0, 0, 0, 0.08);
                "
            >

                <tr>
                    <td style="
                        background: #2f6b3f;
                        padding: 32px;
                        text-align: center;
                    ">
                        <h1 style="
                            margin: 0;
                            color: #ffffff;
                            font-size: 28px;
                            line-height: 1.3;
                        ">
                            Green Garden 🌿
                        </h1>
                    </td>
                </tr>

                <tr>
                    <td style="
                        padding: 40px 32px;
                    ">

                        <h2 style="
                            margin: 0 0 20px 0;
                            color: #222222;
                            font-size: 24px;
                            line-height: 1.3;
                        ">
                            Восстановление пароля
                        </h2>

                        <p style="
                            margin: 0 0 16px 0;
                            color: #555555;
                            font-size: 16px;
                            line-height: 1.6;
                        ">
                            Мы получили запрос на восстановление
                            пароля для вашего аккаунта Green Garden.
                        </p>

                        <p style="
                            margin: 0 0 16px 0;
                            color: #555555;
                            font-size: 16px;
                            line-height: 1.6;
                        ">
                            Нажмите кнопку ниже, чтобы создать
                            новый пароль.
                        </p>

                        <div style="
                            text-align: center;
                            margin: 32px 0;
                        ">
                            <a
                                href="{safe_url}"
                                style="
                                    display: inline-block;
                                    padding: 14px 28px;
                                    background: #2f6b3f;
                                    color: #ffffff;
                                    text-decoration: none;
                                    border-radius: 10px;
                                    font-size: 16px;
                                    font-weight: bold;
                                "
                            >
                                Восстановить пароль
                            </a>
                        </div>

                        <p style="
                            margin: 0 0 16px 0;
                            color: #777777;
                            font-size: 14px;
                            line-height: 1.5;
                        ">
                            Ссылка действительна
                            <strong>
                                {expire_minutes} минут
                            </strong>.
                        </p>

                        <p style="
                            margin: 0;
                            color: #777777;
                            font-size: 14px;
                            line-height: 1.5;
                        ">
                            Если вы не запрашивали восстановление
                            пароля, просто проигнорируйте это письмо.
                            Ваш текущий пароль при этом останется
                            без изменений.
                        </p>

                        <hr style="
                            border: none;
                            border-top: 1px solid #eeeeee;
                            margin: 32px 0;
                        ">

                        <p style="
                            margin: 0 0 10px 0;
                            color: #999999;
                            font-size: 12px;
                            line-height: 1.5;
                        ">
                            Если кнопка не работает, скопируйте
                            следующую ссылку в браузер:
                        </p>

                        <p style="
                            margin: 0;
                            word-break: break-all;
                            color: #2f6b3f;
                            font-size: 12px;
                            line-height: 1.5;
                        ">
                            {safe_url}
                        </p>

                    </td>
                </tr>

                <tr>
                    <td style="
                        background: #f8f8f8;
                        padding: 24px 32px;
                        text-align: center;
                    ">
                        <p style="
                            margin: 0;
                            color: #999999;
                            font-size: 12px;
                            line-height: 1.5;
                        ">
                            © Green Garden. Все права защищены.
                        </p>
                    </td>
                </tr>

            </table>

        </td>
    </tr>
</table>

</body>
</html>
"""


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
