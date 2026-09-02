"""Shared HTTP helper for the public market-data APIs.

All endpoints this project uses are public and unauthenticated. Nothing here
sends credentials or any user identifier.

Rate limits on both providers are undocumented, so 429 and 5xx get an
exponential backoff. Client errors other than 429 are not retried — a 404 is
an answer, not a hiccup.

**429 is not just another retryable status.** A 5xx is the server having a
bad moment and four quick retries is the right answer. A 429 is the server
telling you to stop, and retrying quickly can extend the penalty rather than
clear it. The two therefore have separate attempt budgets: `max_retries`
(short, default 4) for transport errors and 5xx, `rate_limit_retries`
(long, default 8) for 429 alone. A rate limit early in a walk must not leave
a later transport hiccup with nothing left.

Measured on 2026-09-01: `collect size --categories Sports`, single-threaded
at the ~4-5/s that `calibration_harvest`'s profiling established as safe,
raised "429 after 4 attempts" 21 series into a 3,274-series walk. So the
limiter has a *sustained-volume* component and staying under the
instantaneous rate is not sufficient — which every long single-threaded
walk in this repo inherits (`insider_bias/replay.py`, the series-bias
collector, any tier-A replay). For those, the right response to a 429 is
backoff-then-continue, not abort; raise `rate_limit_retries` to buy more of
it.
"""

from __future__ import annotations

import email.utils
import json
import random
import threading
import time

import requests

USER_AGENT = "market-edge-finder/1.0"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

#: Attempt budget for 429 alone. Deliberately larger than `max_retries`:
#: the incident above was a walk dying with retries to spare.
RATE_LIMIT_RETRIES = 8

#: Ceiling on a single backoff sleep. Doubling without a cap means one bad
#: patch puts a multi-hour walk to sleep for longer than the patch lasts.
MAX_BACKOFF = 60.0

#: Upward-only jitter fraction. Several fleet sessions share one limiter, so
#: undithered backoff makes them retry in lockstep — the thundering herd that
#: re-trips the limit they are all waiting out. Bounded below 1.0 so the
#: jittered sequence still increases strictly (base doubles; 1.25 < 2).
JITTER = 0.25

_local = threading.local()


def _session() -> requests.Session:
    """The pooled session for this thread.

    `requests.get` opens a new connection — and so a new TLS handshake —
    for every call. That is invisible on a handful of requests and
    dominant on a walk: profiling `calibration_harvest`'s collector on
    2026-08-29 found **99.5% of its wall clock in per-market candlestick
    GETs at 244ms each**, almost none of it server time. Pooling makes the
    handshake a per-thread one-off.

    Per thread, not global, because `requests.Session` is not thread-safe.
    A caller that fans out across threads gets one session each for free
    and never has to know this exists.
    """
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        _local.session = session
    return session


class HttpError(Exception):
    """A request failed permanently or ran out of retries."""


def _retry_after_seconds(response) -> float | None:
    """Seconds to wait per the response's `Retry-After`, or None.

    RFC 9110 allows either a delay in seconds or an HTTP-date. A header this
    code cannot parse returns None so the caller falls back to backoff — a
    garbage header must never crash a four-hour walk.
    """
    raw = getattr(response, "headers", None)
    value = (raw or {}).get("Retry-After") if hasattr(raw, "get") else None
    if not value:
        return None

    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        pass

    try:
        when = email.utils.parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    return max(0.0, when.timestamp() - time.time())


def get_json(
    url: str,
    params: dict | None = None,
    timeout: int = 30,
    max_retries: int = 4,
    rate_limit_retries: int = RATE_LIMIT_RETRIES,
    max_backoff: float = MAX_BACKOFF,
) -> dict | list:
    """GET a URL and return parsed JSON, retrying transient failures.

    `max_retries` bounds transport errors and 5xx. `rate_limit_retries`
    separately bounds 429s, which honour `Retry-After` when the server sends
    one and otherwise back off exponentially with upward jitter, capped at
    `max_backoff`. A long collector raises `rate_limit_retries` to wait a
    limiter out instead of dying part-way through a walk.
    """
    generic_attempts = 0
    rate_limit_attempts = 0
    generic_delay = 1.0
    rate_limit_delay = 1.0
    last_status: int | None = None

    while True:
        try:
            response = _session().get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.exceptions.RequestException as exc:
            generic_attempts += 1
            if generic_attempts >= max_retries:
                raise HttpError(
                    f"GET {url} failed after {generic_attempts} attempts: {exc}"
                ) from exc
            time.sleep(generic_delay)
            generic_delay = min(generic_delay * 2, max_backoff)
            continue

        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise HttpError(
                    f"GET {url} returned a 200 that was not valid JSON"
                ) from exc

        last_status = response.status_code
        if last_status not in RETRYABLE_STATUS:
            raise HttpError(f"GET {url} failed with status {last_status}")

        if last_status == 429:
            rate_limit_attempts += 1
            if rate_limit_attempts >= rate_limit_retries:
                raise HttpError(
                    f"GET {url} failed with status 429 after "
                    f"{rate_limit_attempts} attempts"
                )
            wait = _retry_after_seconds(response)
            if wait is None:
                wait = min(
                    rate_limit_delay * (1.0 + random.random() * JITTER),
                    max_backoff,
                )
                rate_limit_delay = min(rate_limit_delay * 2, max_backoff)
            time.sleep(wait)
            continue

        generic_attempts += 1
        if generic_attempts >= max_retries:
            raise HttpError(
                f"GET {url} failed with status {last_status} after "
                f"{generic_attempts} attempts"
            )
        time.sleep(generic_delay)
        generic_delay = min(generic_delay * 2, max_backoff)
