import datetime
import math
import secrets
import time

from . import config

DAY_MS = 86400000
WEEK_MS = 7 * DAY_MS          # a rough week (a day or two either way is fine); real week edges come from week_bounds()


def _load_timezone():
    """The one time zone the weeks are counted in. A bad name stops the server at start-up, not on the first Monday."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:                                     # pragma: no cover (Python older than 3.9)
        ZoneInfo = None
    if config.WEEK_TIMEZONE:
        if ZoneInfo is None:
            raise SystemExit("WEEK_TIMEZONE needs Python 3.9 or newer")
        try:
            return ZoneInfo(config.WEEK_TIMEZONE), config.WEEK_TIMEZONE
        except Exception:
            raise SystemExit(f"Unknown WEEK_TIMEZONE {config.WEEK_TIMEZONE!r}. Use a name like America/Mexico_City or UTC.")
    if config.WEEK_TZ_OFFSET_HOURS is not None:
        off = config.WEEK_TZ_OFFSET_HOURS
        return datetime.timezone(datetime.timedelta(hours=off)), f"UTC{off:+g}"
    try:
        return ZoneInfo(config.DEFAULT_WEEK_TIMEZONE), config.DEFAULT_WEEK_TIMEZONE
    except Exception:                                       # a computer without a time-zone database
        # Mexico City has been on UTC-6 all year round since 2022, so a fixed offset is the same thing.
        return datetime.timezone(datetime.timedelta(hours=-6)), config.DEFAULT_WEEK_TIMEZONE + " (UTC-6)"


TZ, TZ_NAME = _load_timezone()


class ApiError(Exception):
    def __init__(self, status, message, data=None, code=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data              # extra fields to send along with the error (a fresh quote, for example)
        self.code = code              # a stable name for the error ("insufficient_funds"), listed in equipo/contratos/errores.md


def bad(message, status=400, code=None):
    return ApiError(status, message, code=code)


def now_ms():
    return int(time.time() * 1000)


def new_id():
    return secrets.token_hex(6)


def round2(x):
    return math.floor(x * 100 + 0.5) / 100


def rand_unit():
    """Cryptographically secure float in (0, 1]."""
    return (secrets.randbelow(2 ** 52) + 1) / 2 ** 52


def rand_below(n):
    return secrets.randbelow(n)


def shuffle(items):
    for i in range(len(items) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def parse_money(value, field="Amount"):
    """Accepts 12, 12.5, '12.5', '$1,200'. No upper limit, only finite numbers."""
    if isinstance(value, bool) or value is None:
        raise bad(f"{field} is required", code="field_required")
    if isinstance(value, str):
        value = value.replace(",", "").replace("$", "").strip()
        if not value:
            raise bad(f"{field} is required", code="field_required")
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise bad(f"{field} must be a number", code="not_a_number")
    if not math.isfinite(x):
        raise bad(f"{field} must be a finite number", code="not_a_number")
    return x


def clean_text(value, field, min_len=1, max_len=200):
    if not isinstance(value, str):
        raise bad(f"{field} is required", code="field_required")
    text = " ".join(value.split())
    if len(text) < min_len:
        raise bad(f"{field} is too short", code="text_too_short")
    if len(text) > max_len:
        raise bad(f"{field} is too long (max {max_len})", code="text_too_long")
    return text


# ---- weeks -------------------------------------------------------------------------
# A week begins on Monday at 00:00:00.000 and ends the following Monday at 00:00:00.000 (exclusive), local time in TZ.
# The key of a week is the date of its Monday, "YYYY-MM-DD". Days and weeks are counted on the calendar, not by adding
# 24 hours, so daylight-saving changes (in zones that have them) cannot move a boundary.

def _midnight_ms(day):
    return int(datetime.datetime(day.year, day.month, day.day, tzinfo=TZ).timestamp() * 1000)


def _local(t):
    return datetime.datetime.fromtimestamp(t / 1000, TZ)


def day_start_ms(t=None):
    return _midnight_ms(_local(now_ms() if t is None else t).date())


def day_key(t=None):
    """The calendar day (in the one time zone the weeks use) as "YYYY-MM-DD"."""
    return _local(now_ms() if t is None else t).date().isoformat()


def next_day_start_ms(t=None):
    """When the calendar day that contains `t` ends: the next local midnight (daylight-saving changes cannot move it)."""
    return _midnight_ms(_local(now_ms() if t is None else t).date() + datetime.timedelta(days=1))


def week_start_ms(t):
    local = _local(t)
    return _midnight_ms(local.date() - datetime.timedelta(days=local.weekday()))


def week_key(t=None):
    local = _local(now_ms() if t is None else t)
    return (local.date() - datetime.timedelta(days=local.weekday())).isoformat()


def week_moment_ms(key, weekday, hour=0):
    """A moment inside the week `key`: `weekday` 0 = Monday ... 6 = Sunday, at `hour`:00 local time in TZ. It is a calendar time, never
    "Monday plus so many hours", so a daylight-saving change cannot move it."""
    day = datetime.date.fromisoformat(key) + datetime.timedelta(days=weekday)
    return int(datetime.datetime(day.year, day.month, day.day, hour, tzinfo=TZ).timestamp() * 1000)


def week_bounds(key):
    first = datetime.date.fromisoformat(key)
    return _midnight_ms(first), _midnight_ms(first + datetime.timedelta(days=7))


def prev_week_key(key):
    start, _ = week_bounds(key)
    return week_key(start - 1)


def next_week_key(key):
    return week_key(week_bounds(key)[1])


def valid_week_key(key):
    try:
        datetime.date.fromisoformat(key)
        return True
    except (TypeError, ValueError):
        return False
