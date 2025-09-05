"""
Theme definitions and helpers for Tkinter GUI.

This module must be import safe: no Tk() or ttk.Style() should be
constructed at import time. Styles are applied in `apply_theme` which
requires a root or toplevel to be passed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple, Optional

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore
import tkinter as tk
from tkinter import ttk


LOGGER = logging.getLogger(__name__)

# Simple theme palette. You can customize these values.
# Define a more soothing colour palette and larger fonts for better readability.
# A dark colour palette inspired by modern ecommerce sites.
# The goal is a sleek, relaxing interface suitable for long use.
THEME = {
    # Background colour for main frames and windows
    "BG": "#12161c",
    # Foreground (text) colour
    "FG": "#e5e7eb",
    # Muted text colour for placeholders or secondary text
    "MUTED": "#9ca3af",
    # Button background and foreground colours
    "BTN_BG": "#3b82f6",  # medium blue
    "BTN_FG": "#ffffff",
    # Card/panel background
    "CARD_BG": "#1f2937",
    # Primary accent colour used for hover/active states
    "ACCENT": "#2563eb",
    # Alternate row background for tables (unused in card view but kept for fallback lists)
    "ALT_BG": "#111827",
    # Typography
    "FONT_FAMILY": "Segoe UI",
    "FONT_SIZE": 11,
}


def apply_theme(root: tk.Widget) -> None:
    """Apply ttk styles to the given root. Must be called after root creation."""
    style = ttk.Style(master=root)
    # Use a base theme to derive our custom dark scheme
    try:
        style.theme_use('clam')
    except Exception:
        pass
    # Frame and labels backgrounds/foregrounds
    style.configure('TFrame', background=THEME["BG"])
    style.configure('TLabel', background=THEME["BG"], foreground=THEME["FG"], font=(THEME["FONT_FAMILY"], THEME["FONT_SIZE"]))
    # Buttons: flat look with subtle hover effect
    style.configure('TButton', background=THEME["BTN_BG"], foreground=THEME["BTN_FG"], font=(THEME["FONT_FAMILY"], THEME["FONT_SIZE"]), padding=(8, 4), relief='flat')
    style.map(
        'TButton',
        background=[('pressed', THEME['ACCENT']), ('active', THEME['ACCENT']), ('!active', THEME['BTN_BG'])],
        foreground=[('disabled', THEME['MUTED']), ('!disabled', THEME['BTN_FG'])],
        relief=[('pressed', 'sunken'), ('!pressed', 'flat')]
    )
    # Treeview (used for some fallback lists)
    style.configure(
        'Treeview',
        font=(THEME['FONT_FAMILY'], THEME['FONT_SIZE']),
        rowheight=28,
        background=THEME['CARD_BG'],
        foreground=THEME['FG'],
        fieldbackground=THEME['CARD_BG'],
        bordercolor=THEME['BG'],
        relief='flat'
    )
    style.configure(
        'Treeview.Heading',
        background=THEME['BG'],
        foreground=THEME['FG'],
        font=(THEME['FONT_FAMILY'], THEME['FONT_SIZE'], 'bold'),
        relief='flat'
    )
    style.map('Treeview.Heading', background=[('active', THEME['ACCENT']), ('!active', THEME['BG'])])
    # Card frame style for material/product cards
    style.configure('Card.TFrame', background=THEME['CARD_BG'], relief='flat', borderwidth=1)
    style.map('Card.TFrame', background=[('active', THEME['CARD_BG'])])
    style.configure('CardTitle.TLabel', background=THEME['CARD_BG'], foreground=THEME['FG'], font=(THEME['FONT_FAMILY'], THEME['FONT_SIZE'] + 1, 'bold'))
    style.configure('CardSubtitle.TLabel', background=THEME['CARD_BG'], foreground=THEME['MUTED'], font=(THEME['FONT_FAMILY'], THEME['FONT_SIZE'] - 1))
    # Card label default style
    style.configure('Card.TLabel', background=THEME['CARD_BG'], foreground=THEME['FG'], font=(THEME['FONT_FAMILY'], THEME['FONT_SIZE']))


def styled_button(master: tk.Widget, **kwargs) -> ttk.Button:
    """Create a button with default style overrides."""
    return ttk.Button(master, **kwargs)


_thumbnail_cache: dict[str, tk.PhotoImage] = {}


def make_thumbnail(path: Optional[str], size: Tuple[int, int] = (64, 64)) -> tk.PhotoImage:
    """
    Load an image and return a Tkinter PhotoImage thumbnail. Caches thumbnails per session.
    Falls back to a blank PhotoImage if PIL is not available or file missing.
    """
    key = f"{path}-{size[0]}x{size[1]}"
    if key in _thumbnail_cache:
        return _thumbnail_cache[key]
    if path and Image and Path(path).exists():
        try:
            img = Image.open(path)
            img.thumbnail(size, Image.ANTIALIAS)
            photo = ImageTk.PhotoImage(img)
            _thumbnail_cache[key] = photo
            return photo
        except Exception as exc:
            LOGGER.warning("Failed to create thumbnail for %s: %s", path, exc)
    # fallback: blank image
    blank = tk.PhotoImage(width=size[0], height=size[1])
    _thumbnail_cache[key] = blank
    return blank


def style_text_widget(widget: tk.Text) -> None:
    """Apply fonts and colors to a Text widget."""
    widget.configure(
        background=THEME["BG"], foreground=THEME["FG"], insertbackground=THEME["FG"],
        font=(THEME["FONT_FAMILY"], THEME["FONT_SIZE"])
    )
