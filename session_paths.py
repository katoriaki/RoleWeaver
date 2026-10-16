"""Filesystem-safe session names for RoleWeaver runtimes."""

import hashlib
import re


def sanitize_session_id(session_id: str) -> str:
    original = (session_id or "default").strip() or "default"
    # Case-fold before hashing so distinct inputs do not alias on Windows.
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", original).lower()
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"COM{i}" for i in range(1, 10))
    reserved.update(f"LPT{i}" for i in range(1, 10))
    if not cleaned.strip(".") or cleaned.split(".", 1)[0].upper() in reserved:
        cleaned = "session"
    cleaned = cleaned.rstrip(".")
    if cleaned != original or len(cleaned) > 100:
        # Retain a digest whenever normalization loses information.
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        cleaned = f"{cleaned[:82]}__{digest}"
    return cleaned
