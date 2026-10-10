"""Settings. Everything can be overridden with environment variables."""
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3000"))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
STATIC_DIR = os.path.join(ROOT, "static")

# Password that unlocks the "add funds" box. Set ADMIN_PASSWORD in the environment
# to change it (do this before you host the site anywhere public).
_DEFAULT_ADMIN_PASSWORD = "local-test-only-password"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)

# CLIQUE_ENV=production is set by the Dockerfile. In production the built-in funds password is
# refused, so a hosted copy can never start with a password that is written in the source code.
PRODUCTION = os.environ.get("CLIQUE_ENV", "").lower() == "production"
if PRODUCTION and (ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD or len(ADMIN_PASSWORD) < 10):
    raise SystemExit(
        "\nRefusing to start: set the ADMIN_PASSWORD environment variable to your own funds password\n"
        "(at least 10 characters, and not the one that ships with the code).\n")


def _start_balance():
    raw = os.environ.get("START_BALANCE", "1000")
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(f"START_BALANCE must be a number, got {raw!r}")
    if not 1 <= value <= 1e9:
        raise SystemExit("START_BALANCE must be between 1 and 1,000,000,000")
    return value


START_BALANCE = _start_balance()    # every new account starts with this much (env START_BALANCE)


def _weekly_bonus():
    raw = os.environ.get("WEEKLY_BONUS", "1000")
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(f"WEEKLY_BONUS must be a number, got {raw!r}")
    if not 0 <= value <= 1e9:
        raise SystemExit("WEEKLY_BONUS must be between 0 and 1,000,000,000 (0 turns it off)")
    return value


WEEKLY_BONUS = _weekly_bonus()      # "passing Go": everyone gets this when a new week starts (env WEEKLY_BONUS, 0 = off)
VOUCHER_AMOUNT = 250.0              # the once-a-week rescue voucher...
VOUCHER_BELOW = 0.5                 # ...for anyone whose cash has dropped below this
SEASON_RESET = os.environ.get("SEASON_RESET", "").strip()   # see backend/seed.py
MIN_BET = 0.1               # smallest allowed bet / stake

# The market maker's depth ("b" in the LMSR). One standard value for every new market: it is deliberately not a setting
# that anybody who proposes a bet can change. Roughly: a stake of this many dollars moves an even market from 50% to 82%.
# Markets created before this was fixed keep whatever depth they were created with, so nobody's holdings are re-priced.
MARKET_LIQUIDITY = 250.0
MAX_DEPOSIT = 1e15          # per "add funds" request
MAX_BALANCE = 1e18          # wallets are clamped here so floats stay sane

# Weeks run from Monday 00:00:00 to the next Monday 00:00:00 (so Sunday 23:59:59.999 is the last moment of a week), in
# one named time zone. Set WEEK_TIMEZONE to any IANA name ("America/Mexico_City", "Europe/Madrid", "UTC"...).
# Older setups used WEEK_TZ_OFFSET_HOURS (a fixed offset such as -6); that still works when WEEK_TIMEZONE is not set.
# With neither set the weeks follow America/Mexico_City.
WEEK_TIMEZONE = os.environ.get("WEEK_TIMEZONE", "").strip()
_tz_env = os.environ.get("WEEK_TZ_OFFSET_HOURS")
WEEK_TZ_OFFSET_HOURS = float(_tz_env) if _tz_env not in (None, "") else None
DEFAULT_WEEK_TIMEZONE = "America/Mexico_City"

# What decides "the person with the least currency" at the end of the week:
#   "netWorth" = cash + what their open positions are worth right now
#   "cash"     = only the cash balance
RANK_BY = os.environ.get("RANK_BY", "netWorth")

# ---- email: for password resets ---------------------------------------------------------------------------------------
# Everybody gives an email address (new accounts must), confirms it with a 6-digit code, and can then reset a forgotten
# password with another code sent to it. Sending needs an email service; set ONE of these on the host (see DEPLOY.md):
#   RESEND_API_KEY            (https://resend.com, a plain web call: works on hosts that block SMTP)
#   BREVO_API_KEY             (https://brevo.com, same idea)
#   SMTP_HOST (+ SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_SECURITY = starttls | ssl | none)
# plus EMAIL_FROM, the address the mail comes from ("Clique <noreply@yourdomain.com>" or just an address the service accepts).
# Without any of them a hosted copy cannot send email (resetting by email says so), and a copy on your own computer prints
# each email in the Terminal window instead, so you can try the whole thing.
EMAIL_FROM = os.environ.get("EMAIL_FROM", "").strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SECURITY = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
RESEND_URL = os.environ.get("RESEND_URL", "https://api.resend.com/emails")          # these two exist so tests can aim at a fake server
BREVO_URL = os.environ.get("BREVO_URL", "https://api.brevo.com/v3/smtp/email")
# New accounts must give an email. (Set EMAIL_REQUIRED=0 to make it optional.)
EMAIL_REQUIRED = os.environ.get("EMAIL_REQUIRED", "1").strip().lower() not in ("0", "false", "no", "off")

SESSION_DAYS = 60
CATEGORIES = ["General", "Sports", "Gaming", "Life", "Money", "Dares", "Music", "Other"]
