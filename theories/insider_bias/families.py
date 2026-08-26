"""insider_bias — ticker-family classifiers shared across this family.

`is_mention_family` is depended on by both theories in this family:
`mention_family` uses it to select its population, and
`insider_judgment`'s full-coverage backtest uses it to define its
complement ("every NON-mention survivor"). Because it is genuinely shared
by both, it lives here in the shared parent rather than in either leaf.

It deliberately does NOT live in `screen.py`: the 2026-08-24 theory split
established that this classifier is not a stage of the screen, and that is
guarded by
`tests/theories/test_insider_bias_screen.py::test_does_not_carry_is_mention_family`.
"""

from __future__ import annotations


def is_mention_family(series_ticker: str) -> bool:
    """True for "will X mention/say/do Y" series.

    Accepts either a series ticker (`KXTRUMPMENTION`) or a full market
    ticker (`KXTRUMPMENTION-26JUL01-MAKE`); the pattern only needs the
    series prefix, which a market ticker always carries.
    """
    return "MENTION" in series_ticker or series_ticker.endswith(("SAY", "ACT"))
