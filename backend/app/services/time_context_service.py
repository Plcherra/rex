from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TimestampValue = Union[str, datetime, None]


class TimeContextService:
    def __init__(
        self,
        timezone_name: Optional[str] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.timezone = self._resolve_timezone(timezone_name)
        self.now_provider = now_provider

    def current_context(
        self,
        now: Optional[datetime] = None,
        previous_timestamp: TimestampValue = None,
    ) -> dict:
        current_time = self._normalized_datetime(now or self._now())
        return {
            "iso_timestamp": current_time.isoformat(),
            "date": current_time.date().isoformat(),
            "weekday": current_time.strftime("%A"),
            "time": current_time.strftime("%H:%M"),
            "timezone": self.timezone_label(current_time),
            "clock_context": self.clock_context(current_time),
            "previous_timestamp_delta": self.delta_from(
                previous_timestamp,
                now=current_time,
            ),
        }

    def clock_context(self, now: Optional[datetime] = None) -> str:
        current_time = self._normalized_datetime(now or self._now())
        return (
            f"{current_time.strftime('%A')} {self._day_period(current_time)} "
            f"({current_time.strftime('%H:%M')} {self.timezone_label(current_time)})"
        )

    def delta_from(
        self,
        previous_timestamp: TimestampValue,
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        previous_time = self.parse_timestamp(previous_timestamp)
        if previous_time is None:
            return None

        current_time = self._normalized_datetime(now or self._now())
        delta_seconds = int((current_time - previous_time).total_seconds())
        if delta_seconds < 0:
            duration = self._human_duration(abs(delta_seconds))
            return duration if duration == "just now" else f"in {duration}"
        if current_time.date() == previous_time.date() and delta_seconds >= 3600:
            return "earlier today"

        duration = self._human_duration(delta_seconds)
        return duration if duration == "just now" else f"{duration} ago"

    def parse_timestamp(self, value: TimestampValue) -> Optional[datetime]:
        if value is None:
            return None

        if isinstance(value, datetime):
            return self._normalized_datetime(value)

        text = str(value).strip()
        if not text:
            return None

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

        return self._normalized_datetime(parsed)

    def timezone_label(self, now: Optional[datetime] = None) -> str:
        current_time = self._normalized_datetime(now or self._now())
        name = getattr(self.timezone, "key", None)
        abbreviation = current_time.tzname()
        if name and abbreviation and name == abbreviation:
            return name
        if name and abbreviation:
            return f"{name} ({abbreviation})"
        if name:
            return name
        if abbreviation:
            return abbreviation
        return str(current_time.tzinfo or timezone.utc)

    def _now(self) -> datetime:
        if self.now_provider is not None:
            return self.now_provider()
        return datetime.now(self.timezone)

    def _normalized_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self.timezone)
        return value.astimezone(self.timezone)

    def _resolve_timezone(self, timezone_name: Optional[str]):
        if timezone_name:
            try:
                return ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                return timezone.utc

        local_timezone = datetime.now().astimezone().tzinfo
        return local_timezone or timezone.utc

    def _day_period(self, value: datetime) -> str:
        hour = value.hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        return "night"

    def _human_duration(self, total_seconds: int) -> str:
        if total_seconds < 60:
            return "just now"

        minutes = total_seconds // 60
        if minutes < 60:
            return self._plural(minutes, "minute")

        hours = minutes // 60
        if hours < 24:
            return self._plural(hours, "hour")

        days = hours // 24
        if days < 14:
            return self._plural(days, "day")

        weeks = days // 7
        if days < 60:
            return f"about {self._plural(weeks, 'week')}"

        months = days // 30
        if days < 365:
            return f"about {self._plural(months, 'month')}"

        years = days // 365
        return f"about {self._plural(years, 'year')}"

    def _plural(self, value: int, unit: str) -> str:
        suffix = "" if value == 1 else "s"
        return f"{value} {unit}{suffix}"
