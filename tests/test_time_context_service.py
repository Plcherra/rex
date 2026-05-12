from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.time_context_service import TimeContextService


def test_current_context_returns_stable_prompt_ready_fields():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    service = TimeContextService(
        timezone_name="America/New_York",
        now_provider=lambda: now,
    )

    context = service.current_context()

    assert context == {
        "iso_timestamp": "2026-05-12T15:30:00-04:00",
        "date": "2026-05-12",
        "weekday": "Tuesday",
        "time": "15:30",
        "timezone": "America/New_York (EDT)",
        "clock_context": "Tuesday afternoon (15:30 America/New_York (EDT))",
        "previous_timestamp_delta": None,
    }


def test_current_context_includes_delta_from_previous_timestamp():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    service = TimeContextService(
        timezone_name="America/New_York",
        now_provider=lambda: now,
    )

    context = service.current_context(previous_timestamp="2026-05-10T22:15:00Z")

    assert context["previous_timestamp_delta"] == "1 day ago"


def test_current_context_can_report_two_day_gap_from_stored_timestamp():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    service = TimeContextService(
        timezone_name="America/New_York",
        now_provider=lambda: now,
    )

    context = service.current_context(previous_timestamp="2026-05-10T15:30:00-04:00")

    assert context["previous_timestamp_delta"] == "2 days ago"


def test_delta_from_reports_same_day_hour_gap_as_earlier_today():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    service = TimeContextService(
        timezone_name="America/New_York",
        now_provider=lambda: now,
    )

    assert service.delta_from("2026-05-12T08:15:00-04:00") == "earlier today"


def test_delta_from_handles_common_past_durations():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=timezone.utc)
    service = TimeContextService(timezone_name="UTC", now_provider=lambda: now)

    assert service.delta_from(now - timedelta(seconds=30)) == "just now"
    assert service.delta_from(now - timedelta(minutes=5)) == "5 minutes ago"
    assert service.delta_from(now - timedelta(hours=26)) == "1 day ago"
    assert service.delta_from(now - timedelta(days=3)) == "3 days ago"
    assert service.delta_from(now - timedelta(days=21)) == "about 3 weeks ago"
    assert service.delta_from(now - timedelta(days=75)) == "about 2 months ago"
    assert service.delta_from(now - timedelta(days=800)) == "about 2 years ago"


def test_delta_from_handles_future_timestamps():
    now = datetime(2026, 5, 12, 15, 30, tzinfo=timezone.utc)
    service = TimeContextService(timezone_name="UTC", now_provider=lambda: now)

    assert service.delta_from(now + timedelta(hours=2)) == "in 2 hours"


def test_missing_or_invalid_timestamp_returns_none():
    service = TimeContextService(
        timezone_name="UTC",
        now_provider=lambda: datetime(2026, 5, 12, 15, 30, tzinfo=timezone.utc),
    )

    assert service.delta_from(None) is None
    assert service.delta_from("") is None
    assert service.delta_from("not-a-timestamp") is None
    assert service.parse_timestamp(None) is None
    assert service.parse_timestamp("not-a-timestamp") is None


def test_parse_timestamp_normalizes_z_suffix_and_naive_datetimes():
    service = TimeContextService(timezone_name="America/New_York")

    z_timestamp = service.parse_timestamp("2026-05-12T19:30:00Z")
    naive_timestamp = service.parse_timestamp(datetime(2026, 5, 12, 15, 30))

    assert z_timestamp.isoformat() == "2026-05-12T15:30:00-04:00"
    assert naive_timestamp.isoformat() == "2026-05-12T15:30:00-04:00"


def test_clock_context_uses_human_day_periods():
    service = TimeContextService(timezone_name="UTC")

    assert (
        service.clock_context(datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc))
        == "Tuesday morning (08:00 UTC)"
    )
    assert (
        service.clock_context(datetime(2026, 5, 12, 15, 0, tzinfo=timezone.utc))
        == "Tuesday afternoon (15:00 UTC)"
    )
    assert (
        service.clock_context(datetime(2026, 5, 12, 19, 0, tzinfo=timezone.utc))
        == "Tuesday evening (19:00 UTC)"
    )
    assert (
        service.clock_context(datetime(2026, 5, 12, 23, 0, tzinfo=timezone.utc))
        == "Tuesday night (23:00 UTC)"
    )


def test_timezone_label_includes_region_and_abbreviation():
    service = TimeContextService(timezone_name="America/New_York")

    label = service.timezone_label(
        datetime(2026, 5, 12, 15, 30, tzinfo=ZoneInfo("America/New_York"))
    )

    assert label == "America/New_York (EDT)"
