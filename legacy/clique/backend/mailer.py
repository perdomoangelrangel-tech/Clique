"""Sending email. Used for the codes that confirm an email address and reset a forgotten password, and nothing else.

Which service is used depends on the settings in config.py: Resend or Brevo (both are a single web request, so they work on
hosts that block ordinary email ports) or any SMTP server. If none is set, a hosted copy cannot send (configured() is False and
the site says so), while a copy on your own computer prints the message in the Terminal window instead of sending it, so the
whole flow can be tried without an account anywhere.

Sending can take seconds or fail, so it always happens on a thread of its own, never while the site is busy with a request.
Nothing here is ever logged with a code in it on a hosted copy.
"""
import json
import smtplib
import ssl
import sys
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

from . import config

TIMEOUT_S = 12
RECENT = []                  # what a copy that is not hosted "sent" (kept in memory for tests and for looking at while developing)
RECENT_KEEP = 50
QUIET = False                # tests switch the Terminal printing off


class MailError(Exception):
    pass


def provider():
    if not config.EMAIL_FROM:
        return None
    if config.RESEND_API_KEY:
        return "resend"
    if config.BREVO_API_KEY:
        return "brevo"
    if config.SMTP_HOST:
        return "smtp"
    return None


def configured():
    return provider() is not None


def delivery_on():
    """Can this copy of the site get a message to somebody? A hosted copy needs a real service; a copy on your own
    computer always can, because it shows the message in the Terminal."""
    return configured() or not config.PRODUCTION


def _sender():
    name, addr = parseaddr(config.EMAIL_FROM)
    return name, addr or config.EMAIL_FROM


def _post_json(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "clique-mailer/1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise MailError(f"the email service answered {e.code}: {detail}")
    except (urllib.error.URLError, OSError) as e:
        raise MailError(f"could not reach the email service: {e}")


def _smtp(to, subject, text):
    name, addr = _sender()
    msg = EmailMessage()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        if config.SMTP_SECURITY == "ssl":
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=TIMEOUT_S, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=TIMEOUT_S)
        with server:
            if config.SMTP_SECURITY == "starttls":
                server.starttls(context=ssl.create_default_context())
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"the email server refused or could not be reached: {e}")


def send(to, subject, text):
    """Sends one plain-text email, right now, on this thread. Raises MailError if it could not be sent."""
    kind = provider()
    if kind == "resend":
        _post_json(config.RESEND_URL, {"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                   {"from": config.EMAIL_FROM, "to": [to], "subject": subject, "text": text})
    elif kind == "brevo":
        name, addr = _sender()
        _post_json(config.BREVO_URL, {"api-key": config.BREVO_API_KEY},
                   {"sender": {"name": name or "Clique", "email": addr}, "to": [{"email": to}], "subject": subject, "textContent": text})
    elif kind == "smtp":
        _smtp(to, subject, text)
    elif config.PRODUCTION:
        raise MailError("no email service is set up on this site")
    else:                                              # your own computer: show it instead of sending it
        RECENT.append({"to": to, "subject": subject, "text": text})
        del RECENT[:-RECENT_KEEP]
        if not QUIET:
            print(f"\n  [email not sent, no email service is set up here]\n  To: {to}\n  Subject: {subject}\n  {text}\n", file=sys.stderr, flush=True)


def send_async(to, subject, text):
    """Sends in the background and never raises: a failure goes to the log (without the message, which holds a code)."""
    def work():
        try:
            send(to, subject, text)
        except MailError as e:
            print(f"  Email to {mask(to)} was not sent: {e}", file=sys.stderr, flush=True)
        except Exception as e:                         # a thread must not die silently
            print(f"  Email to {mask(to)} failed: {e!r}", file=sys.stderr, flush=True)
    t = threading.Thread(target=work, daemon=True)
    t.start()
    return t


def mask(address):
    """a***@gmail.com: enough to recognise your own address, not enough to read somebody else's."""
    local, _, domain = str(address).partition("@")
    return (local[:1] + "***@" + domain) if domain else "***"
