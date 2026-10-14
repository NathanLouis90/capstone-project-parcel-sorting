"""Pace a loop without busy-waiting; callers choose a matching clock."""
import time


def wait_period(delay_time, start_t, clock=time.time, sleep=time.sleep):
    if delay_time <= 0:
        raise ValueError("Control period must be positive")
    remaining = delay_time / 1000 - (clock() - start_t)
    if remaining > 0:
        sleep(remaining)
