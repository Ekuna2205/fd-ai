"""Outgoing e-mail over SMTP. Nothing is sent (and nothing is faked) unless SMTP_HOST and SMTP_FROM are set."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger("faceguard.email")


def send(to: str, subject: str, body: str) -> None:
    """Raises on failure. Callers decide whether to surface or log the error."""
    s = get_settings()
    if not s.smtp_configured:
        raise RuntimeError("SMTP is not configured")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    ctx = ssl.create_default_context()
    if s.smtp_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=ctx)
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
    with server:
        if s.smtp_starttls and not s.smtp_ssl:
            server.starttls(context=ctx)
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)


def send_password_reset(to: str, name: str, token: str) -> None:
    s = get_settings()
    link = f"{s.app_base_url.rstrip('/')}/reset-password?token={token}"
    send(to, "Reset your FaceGuard AI password",
         f"Hello {name},\n\nUse this link to choose a new password. It expires in {s.password_reset_minutes} minutes "
         f"and works once:\n\n{link}\n\nIf you did not ask for this, ignore this e-mail; your password is unchanged.\n")


def send_password_reset_safe(to: str, name: str, token: str) -> None:
    """Background-task wrapper: failures are logged without the token or the address."""
    try:
        send_password_reset(to, name, token)
    except Exception:  # noqa: BLE001
        log.exception("Could not send a password-reset e-mail")
