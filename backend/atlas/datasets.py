"""Access to bundled reference datasets."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def load(name: str) -> dict:
    """Return a deep copy so callers may mutate freely."""
    return copy.deepcopy(_load(name))
