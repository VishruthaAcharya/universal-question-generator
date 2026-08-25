import os
import json
import hashlib
from pathlib import Path
from typing import Any

CACHE_VERSION = "v2"
CACHE_DIR = Path("storage/cache/extractions")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Fast in-memory cache
_MEMORY_CACHE: dict[str, dict[str, Any]] = {}

def compute_file_hash(file_bytes_or_path: bytes | str | Path) -> str:
    """Computes SHA-256 hash of file bytes or file at path."""
    hasher = hashlib.sha256()
    if isinstance(file_bytes_or_path, (str, Path)):
        with open(file_bytes_or_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    else:
        hasher.update(file_bytes_or_path)
    return hasher.hexdigest()

def get_cached_extraction(file_hash: str) -> list[dict[str, Any]] | None:
    """Retrieves cached extraction if valid and matches CACHE_VERSION."""
    # Check in-memory first
    if file_hash in _MEMORY_CACHE:
        entry = _MEMORY_CACHE[file_hash]
        if entry.get("version") == CACHE_VERSION:
            return entry.get("questions")

    # Check file cache
    cache_file = CACHE_DIR / f"{file_hash}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("version") == CACHE_VERSION:
                questions = data.get("questions", [])
                _MEMORY_CACHE[file_hash] = data
                return questions
        except Exception:
            cache_file.unlink(missing_ok=True)

    return None

def save_cached_extraction(file_hash: str, questions: list[dict[str, Any]], metadata: dict[str, Any] | None = None):
    """Saves extraction result to in-memory and persistent disk cache."""
    entry = {
        "version": CACHE_VERSION,
        "file_hash": file_hash,
        "questions": questions,
        "metadata": metadata or {}
    }
    _MEMORY_CACHE[file_hash] = entry

    cache_file = CACHE_DIR / f"{file_hash}.json"
    try:
        cache_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to write extraction cache to disk: {e}")
