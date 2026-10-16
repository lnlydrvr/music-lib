"""Move completed Lucida downloads out of Inbox without losing recovery data."""

from __future__ import annotations

from pathlib import Path


def ingest(filepath: Path, output_dir: Path) -> dict[str, str]:
    """Attempt library placement for a completed Inbox file.

    Conflicts are skipped, while filesystem failures are reported as failures.
    Both outcomes intentionally retain the already-complete Inbox audio.
    """
    path = Path(filepath)
    if not path.is_file():
        return {"status": "fail", "path": "", "inbox_path": str(path), "error": "download_missing"}
    try:
        from src.pipeline import move_to_library_result

        moved = move_to_library_result(path, Path(output_dir))
    except Exception:
        return {"status": "fail", "path": str(path), "inbox_path": str(path), "error": "ingest_failed"}
    if moved.status == "conflict":
        return {"status": "skip", "path": str(path), "inbox_path": str(path), "error": ""}
    if moved.status == "published_source_retained" and moved.path is not None:
        return {"status": "ok", "path": str(moved.path), "inbox_path": str(path), "error": "source_retained"}
    if moved.status != "moved" or moved.path is None:
        return {"status": "fail", "path": str(path), "inbox_path": str(path), "error": "ingest_failed"}
    target = moved.path
    if not Path(target).is_file():
        return {"status": "fail", "path": str(path), "inbox_path": str(path), "error": "ingest_failed"}
    return {"status": "ok", "path": str(target), "inbox_path": str(path), "error": ""}
