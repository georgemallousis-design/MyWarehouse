"""
Offline categorisation logic for security equipment.

The categorizer reads token patterns and token aliases from a DB and
stateless pattern definitions to determine the type of a material.

It uses a simple scoring scheme: each pattern or alias contributes a
weight to a category. The highest scoring category above a threshold
is assigned as auto_category with confidence. Otherwise None.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Tuple, List, Any

import logging

LOGGER = logging.getLogger(__name__)

# Deterministic patterns mapping to categories. Each entry is a tuple of
# (regex pattern, weight, category, label). The weight is added to the
# category score when the pattern matches the material string.
# These are heuristics for common security equipment naming conventions.
CATEGORY_PATTERNS = [
    # Cameras
    (re.compile(r"\bDS-2CD"), 0.6, "Camera", "ds-2cd"),
    (re.compile(r"\bIPC\b", re.IGNORECASE), 0.5, "Camera", "ipc"),
    (re.compile(r"\bIP Cam|IPCam|Bullet|Dome", re.IGNORECASE), 0.4, "Camera", "cam_keyword"),
    # NVR
    (re.compile(r"\bNVR\d*", re.IGNORECASE), 0.6, "NVR", "nvr"),
    (re.compile(r"\bDS-76|DHI-NVR", re.IGNORECASE), 0.5, "NVR", "nvr_prefix"),
    # DVR/XVR
    (re.compile(r"\bDVR\b", re.IGNORECASE), 0.5, "DVR", "dvr"),
    (re.compile(r"\bXVR\b", re.IGNORECASE), 0.5, "DVR", "xvr"),
    # Switches / PoE
    (re.compile(r"\bPoE\b", re.IGNORECASE), 0.3, "Switch", "poe"),
    (re.compile(r"\bSwitch|SG\d", re.IGNORECASE), 0.5, "Switch", "switch"),
    # Sensors
    (re.compile(r"\bSensor\b|PIR|Motion", re.IGNORECASE), 0.5, "Sensor", "sensor"),
    (re.compile(r"\bMagnetic|DoorContact", re.IGNORECASE), 0.4, "Sensor", "doorcontact"),
    # Panels / Keypads
    (re.compile(r"\bPanel\b|Hub|Control|Keypad", re.IGNORECASE), 0.5, "Panel", "panel"),
    (re.compile(r"\bDS-PK", re.IGNORECASE), 0.5, "Panel", "ds-pk"),
    # Access control / locks
    (re.compile(r"\bReader\b|Access|Lock|Strike", re.IGNORECASE), 0.5, "Access Control", "access"),
    # Siren
    (re.compile(r"\bSiren\b|Horn", re.IGNORECASE), 0.5, "Siren", "siren"),
    # Power
    (re.compile(r"\bUPS\b|PSU|Power Supply", re.IGNORECASE), 0.5, "Power", "power"),
]


def normalize(text: str) -> str:
    """Normalize a string by lowercasing and removing non‑alphanumeric characters."""
    text = text.lower()
    # replace greeklish camera synonyms manually
    replacements = {
        "κάμερα": "camera",
        "kamera": "camera",
        "καμερα": "camera",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # remove punctuation and underscores
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # compress whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_family(model: str) -> str:
    """
    Extract a model family prefix (first few tokens or digits) to group materials.
    For example, DS-2CD2343G2-I → DS-2CD2343.
    """
    # Remove trailing letters and numbers after base pattern
    m = re.match(r"([A-Za-z]+-\d+[A-Za-z]*)(.*)", model)
    if m:
        return m.group(1)
    return model.split()[0] if model else ""


def get_alias_map(db: 'Database') -> Dict[str, str]:
    """Load alias tokens from DB. Keys and values are lowercased."""
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT token, category FROM category_aliases")
        return {row[0].lower(): row[1] for row in cur.fetchall()}
    except Exception as e:
        LOGGER.warning("Failed to load category aliases: %s", e)
        return {}


def guess_category(material: Dict[str, Any], db: 'Database') -> Tuple[Optional[str], float, Optional[str], List[str]]:
    """
    Guess the category, confidence and model family for the given material.
    Returns a tuple (category, confidence, family, evidence_list).
    If no category is found, returns (None, 0.0, family, []).
    """
    text = normalize(" ".join(
        [str(material.get(k, "")) for k in ("name", "model", "producer", "description")]
    ))
    family = extract_family(str(material.get("model", "")))
    scores: Dict[str, float] = defaultdict(float)
    evidence: Dict[str, List[str]] = defaultdict(list)
    # Pattern matches
    for pattern, weight, cat, label in CATEGORY_PATTERNS:
        if pattern.search(text):
            scores[cat] += weight
            evidence[cat].append(label)
    # Aliases
    alias_map = get_alias_map(db)
    tokens = set(text.split())
    for token in tokens:
        if token in alias_map:
            cat = alias_map[token]
            scores[cat] += 0.25
            evidence[cat].append(f"alias:{token}")
    if not scores:
        return None, 0.0, family, []
    # choose max
    best_cat = max(scores, key=scores.get)
    confidence = min(1.0, scores[best_cat])
    return best_cat, confidence, family, evidence[best_cat]
