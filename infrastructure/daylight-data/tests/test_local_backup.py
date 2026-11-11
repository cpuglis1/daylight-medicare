import hashlib
import gzip
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("local_backup",Path(__file__).resolve().parents[1]/"tools/backup_local_database.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


@pytest.mark.parametrize("name", ["BACKUP.json", "BACKUP_TOC.txt"])
def test_existing_backup_receipts_cannot_be_replaced(tmp_path, name):
    receipt = tmp_path / name
    receipt.write_bytes(b"sealed earlier receipt")
    with pytest.raises(FileExistsError, match="preserved"):
        backup.require_fresh_receipts(tmp_path)
    assert receipt.read_bytes() == b"sealed earlier receipt"


def test_dangling_receipt_symlink_is_rejected(tmp_path):
    (tmp_path / "BACKUP_TOC.txt").symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError, match="preserved"):
        backup.require_fresh_receipts(tmp_path)


def test_backup_stream_retains_exact_bytes_and_hash(tmp_path):
    content = b"exact public research backup"*1024
    output = io.BytesIO()
    count,digest,minimum = backup.guarded_copy(io.BytesIO(content),output,tmp_path,0,block_size=997)
    assert output.getvalue() == content
    assert count == len(content)
    assert digest == hashlib.sha256(content).hexdigest()
    assert minimum > 0


def test_backup_reserve_rejection_writes_no_first_block(tmp_path,monkeypatch):
    reserve = 7*1024**3
    monkeypatch.setattr(backup.shutil,"disk_usage",lambda p:SimpleNamespace(free=reserve+64*1024**2+1))
    output = io.BytesIO()
    with pytest.raises(RuntimeError,match="reserve"):
        backup.guarded_copy(io.BytesIO(b"too-large-block"),output,tmp_path,reserve)
    assert output.getvalue() == b""


def test_backup_rechecks_reserve_between_blocks(tmp_path,monkeypatch):
    reserve = 7*1024**3
    free = iter([reserve+100*1024**2,reserve+100*1024**2,reserve+64*1024**2+1])
    monkeypatch.setattr(backup.shutil,"disk_usage",lambda p:SimpleNamespace(free=next(free)))
    output = io.BytesIO()
    with pytest.raises(RuntimeError,match="reserve"):
        backup.guarded_copy(io.BytesIO(b"1234567890abcdefghij"),output,tmp_path,reserve,block_size=10)
    assert output.getvalue() == b"1234567890"


@pytest.mark.parametrize("level", [1, 6])
def test_python_outer_gzip_roundtrip_hash_and_trailer(tmp_path, level):
    content = bytes(range(256)) * 17000
    output = io.BytesIO()
    count, digest, minimum = backup.guarded_gzip_stream(io.BytesIO(content), output, tmp_path, 0,
                                                      compresslevel=level, block_size=65537)
    compressed = output.getvalue()
    assert count == len(compressed)
    assert digest == hashlib.sha256(compressed).hexdigest()
    assert gzip.decompress(compressed) == content
    assert minimum > 0
    assert compressed[4:8] == b"\x00\x00\x00\x00"  # deterministic outer header


def test_compressed_writer_hashes_only_written_bytes_and_rechecks_reserve(tmp_path, monkeypatch):
    reserve = 7 * 1024**3
    available = iter([reserve + 100*1024**2, reserve + 100*1024**2, reserve + 64*1024**2 + 1])
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda p: SimpleNamespace(free=next(available)))
    output = io.BytesIO()
    writer = backup.GuardedWriter(output, tmp_path, reserve)
    writer.write(b"compressed-first")
    with pytest.raises(RuntimeError, match="reserve"):
        writer.write(b"compressed-second")
    assert output.getvalue() == b"compressed-first"
    assert writer.count == len(b"compressed-first")
    assert writer.digest.hexdigest() == hashlib.sha256(b"compressed-first").hexdigest()


def test_outer_gzip_reserve_rejection_prevents_first_header_write(tmp_path, monkeypatch):
    reserve = 7 * 1024**3
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda p: SimpleNamespace(free=reserve + 64*1024**2 + 1))
    output = io.BytesIO()
    with pytest.raises(RuntimeError, match="reserve"):
        backup.guarded_gzip_stream(io.BytesIO(b"public-source"), output, tmp_path, reserve)
    assert output.getvalue() == b""


def test_toc_uses_bounded_private_prefix_and_exclusive_private_output(tmp_path, monkeypatch):
    archive = tmp_path / "public.dump.gz"
    with gzip.open(archive, "wb") as handle:
        handle.write(b"PGDMP" + b"x" * (9*1024**2))
    seen = []
    def list_archive(arguments, **kwargs):
        assert arguments[:2] == ["safe-pg-restore", "--list"]
        prefix = Path(arguments[2])
        assert prefix.stat().st_size == 8*1024**2
        assert prefix.stat().st_mode & 0o077 == 0
        seen.append(prefix)
        return SimpleNamespace(stdout="public research TOC\n")
    monkeypatch.setattr(backup.subprocess, "run", list_archive)
    toc = tmp_path / "TOC.txt"
    backup.gzip_archive_toc(archive, "safe-pg-restore", toc)
    assert toc.read_text() == "public research TOC\n"
    assert toc.stat().st_mode & 0o077 == 0
    assert seen and not seen[0].exists()
    with pytest.raises(FileExistsError):
        backup.gzip_archive_toc(archive, "safe-pg-restore", toc)


def test_full_gzip_decode_streams_crc_checked_bytes_without_database_option(tmp_path, monkeypatch):
    archive = tmp_path / "public.dump.gz"
    content = b"PGDMP" + b"public data" * 200000
    archive.write_bytes(gzip.compress(content))
    sink = io.BytesIO()
    class Pipe:
        def write(self, block):
            return sink.write(block)
        def close(self):
            pass
    process = SimpleNamespace(stdin=Pipe(), wait=lambda: 0, poll=lambda: 0)
    def open_decoder(arguments, **kwargs):
        assert arguments == ["safe-pg-restore", "--file=-"]
        assert kwargs["stdout"] == backup.subprocess.DEVNULL
        return process
    monkeypatch.setattr(backup.subprocess, "Popen", open_decoder)
    backup.decode_gzip_archive(archive, "safe-pg-restore", tmp_path / "private.stderr")
    assert sink.getvalue() == content
    damaged = bytearray(archive.read_bytes())
    damaged[-8] ^= 1
    archive.write_bytes(damaged)
    with pytest.raises(gzip.BadGzipFile):
        backup.decode_gzip_archive(archive, "safe-pg-restore", tmp_path / "private.stderr")


@pytest.mark.parametrize("counts", [(363,363,363,0,363), (363,362,362,0,363), (363,363,363,1,363), (363,363,363,0,362)])
def test_backup_completion_guard_counts_only_current_build(tmp_path, counts):
    cursor = SimpleNamespace(fetchone=lambda: counts)
    db = SimpleNamespace(execute=Mock(return_value=cursor))
    if counts == (363,363,363,0,363):
        backup.require_current_execution_complete(db, "current-build")
    else:
        with pytest.raises(ValueError, match="current-build"):
            backup.require_current_execution_complete(db, "current-build")
    statement, parameters = db.execute.call_args.args
    assert "WHERE j.payload->>'build_id'=%s" in statement
    assert "r.controls->>'build_id' IS DISTINCT FROM %s" in statement
    assert parameters == ("current-build",) * 3
