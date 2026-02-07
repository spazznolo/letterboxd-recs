from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from letterboxd_recs.util.ratelimit import sleep_seconds

T = TypeVar("T")


def retry(
    func: Callable[[], T],
    attempts: int = 3,
    delay_seconds: float = 1.0,
    on_error: Callable[[Exception, int], None] | None = None,
) -> T:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if on_error:
                on_error(exc, attempt)
            if attempt < attempts and delay_seconds > 0:
                sleep_seconds(delay_seconds)
    raise RuntimeError("retry failed") from last_error
