"""Shared HTTP helper for the public market-data APIs.

All endpoints this project uses are public and unauthenticated. Nothing here
sends credentials or any user identifier.

Rate limits on both providers are undocumented, so 429 and 5xx get an
exponential backoff. Client errors other than 429 are not retried — a 404 is
an answer, not a hiccup.
"""

from __future__ import annotations

import json
import time

import requests

USER_AGENT = "market-edge-finder/1.0"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpError(Exception):
    """A request failed permanently or ran out of retries."""


def get_json(
    url: str,
    params: dict | None = None,
    timeout: int = 30,
    max_retries: int = 4,
) -> dict | list:
    """GET a URL and return parsed JSON, retrying transient failures."""
    delay = 1.0
    last_status: int | None = None

    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.exceptions.RequestException as exc:
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise HttpError(
                f"GET {url} failed after {max_retries} attempts: {exc}"
            ) from exc

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

        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= 2

    raise HttpError(
        f"GET {url} failed with status {last_status} after {max_retries} attempts"
    )
