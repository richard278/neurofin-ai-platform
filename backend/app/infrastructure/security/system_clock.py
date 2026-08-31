from datetime import UTC, datetime

from app.application.security.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)
