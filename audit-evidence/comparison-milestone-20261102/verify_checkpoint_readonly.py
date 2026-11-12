"""Verify the exact sealed artifacts listed in this dated milestone checkpoint.

This is an integrity replay, not a test runner, source interpretation review,
database operation or certification of the current application process.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    inputs = json.loads((HERE / "CHECKPOINT_INPUTS_R1.json").read_text())
    checks = 0
    members_checked = 0
    unique_members = set()
    packets = []
    for packet in inputs["sealed_packets"]:
        manifest = ROOT / packet["path"]
        assert digest(manifest) == packet["sha256"], packet["path"]
        checks += 1
        document = json.loads(manifest.read_text())
        members = document.get("members", document.get("files"))
        assert isinstance(members, list) and members, packet["path"]
        checks += 1
        for member in members:
            path = Path(member["path"])
            if path.is_absolute():
                target = path
            elif path.parts[0] in {"docs", "audit-evidence", "cms-slice", "infrastructure", "alternatives"}:
                target = ROOT / path
            else:
                target = manifest.parent / path
            assert target.is_file(), str(target)
            assert digest(target) == member["sha256"], str(target)
            assert target.stat().st_size == member["bytes"], str(target)
            checks += 3
            members_checked += 1
            unique_members.add(str(target))
        packets.append({"path": packet["path"], "members_replayed": len(members)})
    for receipt in inputs["bound_receipts"]:
        path = ROOT / receipt["path"]
        assert digest(path) == receipt["sha256"], receipt["path"]
        assert path.stat().st_size == receipt["bytes"], receipt["path"]
        checks += 2
    return {
        "schema": "daylight.comparison-milestone.checkpoint-integrity-replay.r1",
        "checks_passed": checks,
        "sealed_packets_replayed": packets,
        "member_occurrences_checked": members_checked,
        "unique_resolved_members_checked": len(unique_members),
        "milestone_complete": False,
        "source_meaning_from_integrity_replay": False,
        "current_runtime_certified": False,
        "new_acceptance": False,
        "database_or_network_connection": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
