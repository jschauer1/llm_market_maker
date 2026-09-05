"""Pinned payout-station metadata for the frozen WG-1 campaign.

Coordinates and elevation are the values returned by the NWS station API.
The CLI identifiers are independently checked against TWC's Kalshi station
metadata by the collector before any event is normalized.
"""

STATIONS = {
    "KXHIGHNY": {
        "station": "KNYC",
        "latitude": 40.78333,
        "longitude": -73.96667,
        "elevation": 46.9392,
        "standard_utc_offset_hours": -5,
        "cli_id": "NYC",
    },
    "KXHIGHLAX": {
        "station": "KLAX",
        "latitude": 33.93806,
        "longitude": -118.38889,
        "elevation": 38.1,
        "standard_utc_offset_hours": -8,
        "cli_id": "LAX",
    },
    "KXHIGHCHI": {
        "station": "KMDW",
        "latitude": 41.78417,
        "longitude": -87.75528,
        "elevation": 188.0616,
        "standard_utc_offset_hours": -6,
        "cli_id": "MDW",
    },
}

