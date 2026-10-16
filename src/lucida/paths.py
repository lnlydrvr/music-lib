"""Filesystem locations used by the Lucida adapter."""

from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "music-lib"
CLEARANCE_PATH = CONFIG_DIR / "lucida_clearance.json"
LOG_PATH = CONFIG_DIR / "lucida.log"
