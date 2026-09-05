"""News-drift theory package."""

from theories.news_drift.signal import MoveSignal, detect
from theories.news_drift.theory import NewsDriftTheory

THEORY = NewsDriftTheory()

__all__ = ["MoveSignal", "NewsDriftTheory", "THEORY", "detect"]
