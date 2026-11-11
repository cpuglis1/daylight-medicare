"""Immutable content archive. Logical occurrences live separately from exact bytes."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import sys
from typing import BinaryIO


@dataclass(frozen=True)
class ArchivedObject:
    sha256: str
    byte_length: int
    object_key: str
    reused: bool


def object_key(digest: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid content hash")
    return f"evidence/sha256/{digest[:2]}/{digest}"


def hash_stream(stream: BinaryIO) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
        size += len(block)
    return digest.hexdigest(), size


class FileArchive:
    def __init__(self, root: Path, reserve_bytes: int = 0):
        self.root = root.resolve()
        if reserve_bytes < 0:
            raise ValueError("Invalid archive disk reserve")
        self.reserve_bytes = reserve_bytes
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if stat.S_IMODE(self.root.stat().st_mode) & 0o077:
            raise ValueError("Archive root must be private (mode 0700)")

    def require_space(self, additional_bytes=0):
        if self.reserve_bytes and shutil.disk_usage(self.root).free < self.reserve_bytes + additional_bytes:
            raise RuntimeError("Archive capture reached configured disk reserve")

    def path(self, digest: str) -> Path:
        path = self.root / object_key(digest)
        # A symlink inside the private archive cannot redirect a content write/read.
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Archive path escapes configured root")
        for parent in (path, *path.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                raise ValueError("Symlink in archive path")
        return path

    def put(self, stream: BinaryIO, expected_sha256: str | None = None,
            max_bytes: int = 10 * 1024**3) -> ArchivedObject:
        # Spool in the same filesystem for atomic hard-link create-if-absent.
        fd, temporary = tempfile.mkstemp(prefix="capture-", dir=self.root)
        digest, size = hashlib.sha256(), 0
        try:
            with os.fdopen(fd, "wb") as handle:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    self.require_space(len(block))
                    size += len(block)
                    if size > max_bytes:
                        raise ValueError("Capture exceeds configured byte bound")
                    digest.update(block)
                    handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
            self.require_space()
            sha = digest.hexdigest()
            if expected_sha256 is not None and expected_sha256 != sha:
                raise ValueError("Capture hash mismatch")
            target = self.path(sha)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            reused = False
            try:
                os.link(temporary, target)
                os.chmod(target, 0o400)
                parent_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except FileExistsError:
                self.verify(sha)
                reused = True
            return ArchivedObject(sha, size, object_key(sha), reused)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def put_file(self, source: Path, expected_sha256: str,
                 max_bytes: int = 10 * 1024**3) -> ArchivedObject:
        """APFS copy-on-write capture; never a hard link to a mutable source.

        A clone has an independent inode and diverges on writes. Verify its entire
        contents before atomic archive publication. Other platforms/filesystems
        retain the normal bounded streaming capture implementation.
        """
        source = Path(source).resolve(strict=True)
        self.require_space(128 * 1024**2)
        if source.stat().st_size > max_bytes:
            raise ValueError("Capture exceeds configured byte bound")
        # Avoid spooling another copy when exact bytes are already captured.
        existing = self.path(expected_sha256)
        if existing.exists():
            size = self.verify(expected_sha256)
            with source.open("rb") as handle:
                actual, source_size = hash_stream(handle)
            if actual != expected_sha256 or source_size != size:
                raise ValueError("Capture hash mismatch")
            return ArchivedObject(actual, size, object_key(actual), True)
        if sys.platform == "darwin":
            with tempfile.TemporaryDirectory(prefix="clone-", dir=self.root) as directory:
                temporary = Path(directory) / "object"
                libc = ctypes.CDLL(None, use_errno=True)
                clone = libc.clonefile
                clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
                clone.restype = ctypes.c_int
                result = clone(os.fsencode(source), os.fsencode(temporary), 0)
                if result == 0:
                    with temporary.open("rb") as handle:
                        actual, size = hash_stream(handle)
                        os.fsync(handle.fileno())
                    self.require_space()
                    if actual != expected_sha256 or size > max_bytes:
                        raise ValueError("Capture hash mismatch or configured byte bound exceeded")
                    os.chmod(temporary, 0o400)
                    target = self.path(actual)
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    reused = False
                    try:
                        os.link(temporary, target)
                        fd = os.open(target.parent, os.O_RDONLY)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                    except FileExistsError:
                        self.verify(actual)
                        reused = True
                    return ArchivedObject(actual, size, object_key(actual), reused)
                code = ctypes.get_errno()
                if code not in (errno.ENOTSUP, errno.EXDEV, errno.EINVAL, errno.ENOSYS):
                    raise OSError(code, os.strerror(code), str(source))
        with source.open("rb") as handle:
            return self.put(handle, expected_sha256, max_bytes)

    def verify(self, digest: str) -> int:
        with self.path(digest).open("rb") as handle:
            actual, size = hash_stream(handle)
        if actual != digest:
            raise ValueError("Existing archive object is corrupt; refusing reuse")
        return size

    def open(self, digest: str):
        self.verify(digest)
        return self.path(digest).open("rb")


class S3Archive:
    """S3 conditional creation; no bucket creation, public ACL or credentials in code.

    Cloud round-trip must be proven on the selected actual account before deployment.
    This adapter does not claim Object Lock or a retention policy is configured.
    """
    def __init__(self, client, bucket: str, prefix: str = ""):
        self.client, self.bucket, self.prefix = client, bucket, prefix.strip("/")

    def put(self, stream: BinaryIO, expected_sha256: str | None = None,
            max_bytes: int = 5 * 1024**3) -> ArchivedObject:
        # S3 single PUT is <=5GiB. Multipart support is a separate unimplemented path.
        with tempfile.TemporaryFile() as handle:
            digest, size = hashlib.sha256(), 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                if size > min(max_bytes, 5 * 1024**3):
                    raise ValueError("Capture exceeds single-PUT bound")
                digest.update(block)
                handle.write(block)
            sha = digest.hexdigest()
            if expected_sha256 is not None and sha != expected_sha256:
                raise ValueError("Capture hash mismatch")
            key = "/".join(filter(None, [self.prefix, object_key(sha)]))
            handle.seek(0)
            from botocore.exceptions import ClientError
            import base64
            try:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=handle,
                    ContentLength=size, IfNoneMatch="*", ServerSideEncryption="AES256",
                    ChecksumSHA256=base64.b64encode(bytes.fromhex(sha)).decode(),
                    Metadata={"sha256": sha})
                reused = False
            except ClientError as error:
                if error.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
                    raise
                existing = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
                try:
                    actual, actual_size = hash_stream(existing)
                finally:
                    existing.close()
                if actual != sha or actual_size != size:
                    raise ValueError("Existing S3 object failed exact byte verification")
                reused = True
            return ArchivedObject(sha, size, key, reused)
