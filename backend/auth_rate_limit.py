"""In-memory brute-force protection for TaxFlow Pro authentication endpoints.

Tracks failed login attempts per username in memory only. Progressive delay is
enforced via HTTP 429 with a Retry-After header. A hard lockout after 10
consecutive failures persists until the application process restarts.

No state is written to disk, so a process restart resets all counters.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status


#: Maximum consecutive failures before hard lockout until process restart.
MAX_FAILED_ATTEMPTS = 10

#: progressive delay schedule (in seconds) for the *next* attempt after N failures.
# After 1 failure -> next attempt delayed 1s; 2 failures -> 2s; 3 -> 4s; ...
def _delay_for_attempts(failed_attempts: int) -> int:
    if failed_attempts <= 0:
        return 0
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        return -1  # signal lockout
    # After 1 failure -> next attempt delayed 1s; 2 failures -> 2s; 3 -> 4s; ...
    return 2 ** max(0, failed_attempts - 1)


class _AttemptRecord:
    __slots__ = ("failed_attempts", "last_attempt", "lockout_until")

    def __init__(self) -> None:
        self.failed_attempts: int = 0
        self.last_attempt: Optional[datetime] = None
        self.lockout_until: Optional[datetime] = None


# Global in-memory tracker. Intentionally not persisted to disk.
_tracker: dict[str, _AttemptRecord] = {}


def _get_record(username: str) -> _AttemptRecord:
    username = username.lower()
    if username not in _tracker:
        _tracker[username] = _AttemptRecord()
    return _tracker[username]


def check_login_attempt(username: str) -> None:
    """Validate that the given username is not currently rate-limited.

    Raises HTTPException(429) with Retry-After when a progressive delay or
    hard lockout is active. Updates `last_attempt` to the current time so the
    next request measures elapsed time from when this request was received.
    """
    record = _get_record(username)
    now = datetime.now(timezone.utc)

    if record.lockout_until and record.lockout_until > now:
        retry_after = max(1, int((record.lockout_until - now).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Clear an expired lockout so the user gets the progressive-delay path.
    if record.lockout_until and record.lockout_until <= now:
        record.lockout_until = None

    if record.failed_attempts >= MAX_FAILED_ATTEMPTS:
        # Hard lockout: require process restart. Use a distant future timestamp.
        record.lockout_until = now + timedelta(days=365)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(86400)},
        )

    required_delay = _delay_for_attempts(record.failed_attempts)
    if required_delay > 0:
        last = record.last_attempt
        if last is not None:
            elapsed = (now - last).total_seconds()
            remaining = required_delay - elapsed
            if remaining > 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Please try again later.",
                    headers={"Retry-After": str(int(remaining) + 1)},
                )

    # Only stamp last_attempt for requests that are allowed through. Rate-limited
    # requests do not advance the clock, so the same delay applies to repeated
    # rapid retries.
    record.last_attempt = now


def record_login_failure(username: str) -> None:
    """Increment the failure counter for a username after a failed login."""
    record = _get_record(username)
    record.failed_attempts += 1
    record.last_attempt = datetime.now(timezone.utc)

    if record.failed_attempts >= MAX_FAILED_ATTEMPTS:
        record.lockout_until = datetime.now(timezone.utc) + timedelta(days=365)


def record_login_success(username: str) -> None:
    """Reset the failure counter for a username after a successful login."""
    username = username.lower()
    if username in _tracker:
        _tracker[username].failed_attempts = 0
        _tracker[username].lockout_until = None
        _tracker[username].last_attempt = None


def get_attempt_state(username: str) -> dict:
    """Return the current in-memory attempt state (exposed for tests/debug)."""
    record = _get_record(username)
    return {
        "failed_attempts": record.failed_attempts,
        "last_attempt": record.last_attempt.isoformat() if record.last_attempt else None,
        "lockout_until": record.lockout_until.isoformat() if record.lockout_until else None,
    }


def reset_attempts(username: str) -> None:
    """Manually reset attempts for a username (tests only)."""
    username = username.lower()
    if username in _tracker:
        del _tracker[username]
