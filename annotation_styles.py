"""Helper to load annotation styles once at startup.

Loads `annotation_styles.json` from the repository root (same directory)
and exposes `styles` dict and `CURRENT_STYLE_INDEX` constant.

The JSON file uses string keys ("0","1",...) so we convert them to ints
for convenient lookup: styles.get(CURRENT_STYLE_INDEX, styles.get(0)).
"""
from __future__ import annotations

import json
import os
from typing import Dict, Any

# Active style index (change this to select a different style at startup)
CURRENT_STYLE_INDEX: int = 1


def _load_styles() -> Dict[int, Dict[str, Any]]:
    path = os.path.join(os.path.dirname(__file__), "annotation_styles.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
            # normalize keys to int
            return {int(k): v for k, v in (raw or {}).items()}
    except Exception:
        # fallback single default style
        return {
            0: {
                "name": "Default",
                "dimtxt": 3.0,
                "dimasz": 2.0,
                "dimexe": 1.0,
                "dimexo": 1.0,
                "dimtad": 1,
                "dimtofl": 1,
                "text_height": 3.0,
                "text_style": "Standard",
                "color": 7,
            }
        }


styles: Dict[int, Dict[str, Any]] = _load_styles()


def get_active_style() -> Dict[str, Any]:
    """Return the active style dict based on CURRENT_STYLE_INDEX.

    Falls back to style 0 when the chosen index is missing.
    """
    return styles.get(CURRENT_STYLE_INDEX, styles.get(0, {}))
