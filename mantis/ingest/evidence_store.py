"""Content-addressed local storage for original evidence files."""

import hashlib
import os
import tempfile
from pathlib import Path


def evidence_root() -> Path:
    configured = os.getenv("MANTIS_EVIDENCE_DIR", "./evidence")
    return Path(configured).expanduser().resolve()


def store_evidence(content: bytes) -> tuple[str, str]:
    """Store exact uploaded bytes and return (SHA-256, relative storage key)."""
    digest = hashlib.sha256(content).hexdigest()
    root = evidence_root()
    target_dir = root / digest[:2]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / digest

    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise OSError("Existing content-addressed evidence failed its hash check")
    else:
        fd, temp_name = tempfile.mkstemp(prefix=".upload-", dir=target_dir)
        try:
            with os.fdopen(fd, "wb") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            # Atomic replacement prevents readers from seeing a partial evidence file.
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    return digest, target.relative_to(root).as_posix()


def read_evidence(digest: str) -> bytes:
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        raise ValueError("Invalid evidence SHA-256")
    path = evidence_root() / digest[:2] / digest
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest.lower():
        raise OSError("Evidence failed its SHA-256 integrity check")
    return content
