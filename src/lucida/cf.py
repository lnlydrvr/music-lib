"""Cloudflare clearance acquisition for Lucida."""

import importlib
import json
import math
import re
import time
import os
import tempfile
from pathlib import Path

from src.lucida.paths import CLEARANCE_PATH

CLEARANCE_TTL = 24 * 60 * 60


class ClearanceAccessError(RuntimeError):
    """Raised when a browser-based Lucida access challenge cannot be cleared."""


def chromium_installed() -> bool:
    """Return whether the Playwright Chromium executable is installed."""
    try:
        sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
    except (ImportError, OSError, AttributeError, RuntimeError):
        return False


def load_clearance() -> tuple[str | None, str | None]:
    """Load clearance token and user agent, returning empty values if invalid."""
    try:
        path = Path(CLEARANCE_PATH)
        if os.name == "posix" and path.stat().st_mode & 0o077:
            return None, None
        data = json.loads(path.read_text(encoding="utf-8"))
        token, ua, timestamp = data.get("cf_clearance"), data.get("ua"), data.get("ts")
        if (
            isinstance(token, str)
            and token
            and isinstance(ua, str)
            and ua
            and isinstance(timestamp, (int, float))
            and not isinstance(timestamp, bool)
            and math.isfinite(timestamp)
            and 0 <= time.time() - timestamp <= CLEARANCE_TTL
        ):
            return token, ua
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return None, None


def save_clearance(cf_clearance: str, ua: str) -> None:
    """Persist clearance credentials in the per-user configuration directory."""
    path = Path(CLEARANCE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.parent.chmod(0o700)
    payload = json.dumps({"cf_clearance": cf_clearance, "ua": ua, "ts": time.time()})
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600) if os.name == "posix" else None
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            path.chmod(0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def acquire(visible: bool = True) -> tuple[str, str]:
    """Open a visible Chromium window for the user to clear Lucida's challenge.

    The deadline bounds browser launch, navigation, and challenge polling.
    Synchronous Playwright startup/shutdown and context cleanup cannot be
    interrupted reliably, so cleanup may extend beyond that deadline.
    """
    if not visible:
        raise ClearanceAccessError("Lucida clearance requires a visible browser window.")
    try:
        deadline = time.monotonic() + 180
        sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
        with sync_playwright() as playwright:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ClearanceAccessError("Cloudflare challenge was not completed before timeout.")
            profile_dir = Path(CLEARANCE_PATH).parent / "lucida-browser"
            config_dir = Path(CLEARANCE_PATH).parent
            if os.name == "posix" and config_dir.exists():
                config_dir.chmod(0o700)
            profile_dir.mkdir(parents=True, exist_ok=True)
            if os.name == "posix":
                profile_dir.chmod(0o700)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                timeout=max(1, int(remaining * 1000)),
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ClearanceAccessError("Cloudflare challenge was not completed before timeout.")
                page.goto("https://lucida.to", wait_until="domcontentloaded", timeout=max(1, int(remaining * 1000)))
                token = None
                while time.monotonic() < deadline:
                    token = next(
                        (cookie["value"] for cookie in context.cookies("https://lucida.to") if cookie.get("name") == "cf_clearance"),
                        None,
                    )
                    if token:
                        ua = page.evaluate("() => navigator.userAgent")
                        save_clearance(token, ua)
                        return token, ua
                    page.wait_for_timeout(min(1000, max(1, int((deadline - time.monotonic()) * 1000))))
                raise ClearanceAccessError("Cloudflare challenge was not completed before timeout.")
            finally:
                # Playwright's synchronous close is not safely cancellable.
                context.close()
    except ClearanceAccessError:
        raise
    except (ImportError, ModuleNotFoundError):
        raise
    except Exception as exc:
        raise ClearanceAccessError("Unable to access Lucida.") from exc
