"""When a week begins and ends: Monday 00:00:00 to the next Monday 00:00:00 in one named time zone."""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config, util   # noqa: E402

try:
    from zoneinfo import ZoneInfo
    ZoneInfo("America/New_York")
    HAVE_TZ = True
except Exception:                   # a computer without a time-zone database
    HAVE_TZ = False


def ms(y, mo, d, h=0, mi=0, s=0, ms_=0, tz=None):
    return int(datetime.datetime(y, mo, d, h, mi, s, ms_ * 1000, tzinfo=tz or util.TZ).timestamp() * 1000)


class WeekBoundaries(unittest.TestCase):
    def test_the_default_is_mexico_city(self):
        if "WEEK_TIMEZONE" not in os.environ and "WEEK_TZ_OFFSET_HOURS" not in os.environ:
            self.assertTrue(util.TZ_NAME.startswith("America/Mexico_City"))
        self.assertEqual(config.DEFAULT_WEEK_TIMEZONE, "America/Mexico_City")

    def test_a_week_starts_monday_midnight_and_ends_the_next_monday_midnight(self):
        # Monday 28 Sep 2026 is the Monday of the week containing Sunday 4 Oct 2026
        self.assertEqual(util.week_key(ms(2026, 9, 28, 0, 0, 0)), "2026-09-28")
        self.assertEqual(util.week_key(ms(2026, 10, 4, 23, 59, 59, 999)), "2026-09-28")
        self.assertEqual(util.week_key(ms(2026, 10, 5, 0, 0, 0)), "2026-10-05")
        self.assertEqual(util.week_key(ms(2026, 9, 27, 23, 59, 59, 999)), "2026-09-21")
        start, end = util.week_bounds("2026-09-28")
        self.assertEqual((start, end), (ms(2026, 9, 28), ms(2026, 10, 5)))
        self.assertEqual(util.week_key(start), "2026-09-28")
        self.assertEqual(util.week_key(end - 1), "2026-09-28")
        self.assertEqual(util.week_key(end), "2026-10-05")

    def test_every_weekday_belongs_to_its_weeks_monday(self):
        for day in range(28, 32):
            self.assertEqual(util.week_key(ms(2026, 12, day, 12)), "2026-12-28")
        for day in range(1, 4):
            self.assertEqual(util.week_key(ms(2027, 1, day, 12)), "2026-12-28")

    def test_next_and_previous_week(self):
        self.assertEqual(util.next_week_key("2026-09-28"), "2026-10-05")
        self.assertEqual(util.prev_week_key("2026-09-28"), "2026-09-21")
        self.assertEqual(util.next_week_key(util.prev_week_key("2026-01-05")), "2026-01-05")

    def test_the_mexico_city_wall_clock_decides_not_utc(self):
        with mock.patch.object(util, "TZ", datetime.timezone(datetime.timedelta(hours=-6))):
            utc_monday_early = int(datetime.datetime(2026, 10, 5, 3, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)   # Sunday 21:00 in Mexico City
            self.assertEqual(util.week_key(utc_monday_early), "2026-09-28")
            utc_monday_6 = int(datetime.datetime(2026, 10, 5, 6, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)       # Monday 00:00 in Mexico City
            self.assertEqual(util.week_key(utc_monday_6), "2026-10-05")

    def test_the_start_of_a_day(self):
        self.assertEqual(util.day_start_ms(ms(2026, 10, 3, 17, 30)), ms(2026, 10, 3))

    @unittest.skipUnless(HAVE_TZ, "no time-zone database on this computer")
    def test_daylight_saving_cannot_move_a_boundary(self):
        ny = ZoneInfo("America/New_York")
        with mock.patch.object(util, "TZ", ny):
            start, end = util.week_bounds("2026-03-02")          # the week that springs forward on Sunday 8 March
            self.assertEqual(start, ms(2026, 3, 2, tz=ny))
            self.assertEqual(end, ms(2026, 3, 9, tz=ny))
            self.assertEqual((end - start) / 3600000, 167.0)     # one hour shorter that week
            self.assertEqual(util.week_key(end - 1), "2026-03-02")
            self.assertEqual(util.week_key(end), "2026-03-09")
            start, end = util.week_bounds("2026-10-26")          # the week that falls back on Sunday 1 November
            self.assertEqual((end - start) / 3600000, 169.0)
            self.assertEqual(util.next_week_key("2026-10-26"), "2026-11-02")


class ChoosingTheZone(unittest.TestCase):
    def pick(self, tz="", offset=None):
        with mock.patch.object(config, "WEEK_TIMEZONE", tz), mock.patch.object(config, "WEEK_TZ_OFFSET_HOURS", offset):
            return util._load_timezone()

    def test_an_explicit_zone_wins(self):
        _, name = self.pick("UTC") if HAVE_TZ else (None, "UTC")
        self.assertEqual(name, "UTC")

    def test_the_old_fixed_offset_setting_still_works(self):
        tz, name = self.pick("", -6.0)
        self.assertEqual(tz.utcoffset(None), datetime.timedelta(hours=-6))
        tz, _ = self.pick("", 5.5)
        self.assertEqual(tz.utcoffset(None), datetime.timedelta(hours=5.5))

    def test_with_neither_it_is_mexico_city(self):
        _, name = self.pick("", None)
        self.assertTrue(name.startswith("America/Mexico_City"))

    def test_a_misspelt_zone_stops_the_server_instead_of_guessing(self):
        with self.assertRaises(SystemExit):
            self.pick("Mars/Olympus_Mons")


if __name__ == "__main__":
    unittest.main()
