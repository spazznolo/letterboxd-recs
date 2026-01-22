import time


def sleep_seconds(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
