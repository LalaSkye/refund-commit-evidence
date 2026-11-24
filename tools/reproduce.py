#!/usr/bin/env python3
"""Verify and replay the archived delayed-withdrawal checkpoint."""

import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "evidence" / "delayed-withdrawal-local.zip"
ARCHIVE_HASH = ROOT / "evidence" / "ARCHIVE.sha256"
HEX_HASH = re.compile(r"[0-9a-f]{64}")
LABELS = (
    "withdrawal committed upstream, delivery delayed, source unavailable",
    "withdrawal delivered, source available, identical retry",
    "matched active approval, current source available",
    "deliberate cached-approval control, effect detected after withdrawal",
)


class Mismatch(Exception):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def extract_archive(destination):
    expected_hash = ARCHIVE_HASH.read_text(encoding="ascii").strip()
    require(HEX_HASH.fullmatch(expected_hash), "invalid ARCHIVE.sha256")
    actual_hash = digest(ARCHIVE)
    require(actual_hash == expected_hash,
            f"archive SHA-256: expected {expected_hash}, got {actual_hash}")

    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set()
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            require(
                member.filename not in names
                and "\\" not in member.filename
                and not path.is_absolute()
                and ".." not in path.parts
                and ":" not in member.filename
                and (member.external_attr >> 16) & 0o170000 != 0o120000,
                f"unsafe or duplicate archive path: {member.filename!r}",
            )
            names.add(member.filename)
        archive.extractall(destination)


def verify_checksums(destination):
    lines = (destination / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    require(lines, "SHA256SUMS is empty")
    checked = set()
    for number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match, f"invalid SHA256SUMS line {number}")
        expected, name = match.groups()
        path = PurePosixPath(name)
        require(
            not path.is_absolute() and ".." not in path.parts
            and "\\" not in name and ":" not in name and name not in checked,
            f"unsafe or duplicate SHA256SUMS path on line {number}: {name!r}",
        )
        checked.add(name)
        actual = digest(destination.joinpath(*path.parts))
        require(actual == expected,
                f"SHA256SUMS line {number} ({name}): expected {expected}, got {actual}")
    files = {path.relative_to(destination).as_posix()
             for path in destination.rglob("*") if path.is_file()}
    require(checked == files - {"SHA256SUMS"},
            f"SHA256SUMS file coverage mismatch: {sorted(checked ^ (files - {'SHA256SUMS'}))}")


def replay(destination):
    records = (destination / "RUN.jsonl").read_text(encoding="utf-8").splitlines()
    require(len(records) == 5, f"RUN.jsonl: expected 5 lines, got {len(records)}")
    captured = [json.loads(line) for line in records]
    require(isinstance(captured[0], dict), "RUN.jsonl: invalid header")
    request_hash = captured[0].get("request_sha256")
    require(isinstance(request_hash, str) and HEX_HASH.fullmatch(request_hash),
            "RUN.jsonl: invalid request_sha256")
    effect = [["refund-001", 2500, "GBP", request_hash]]
    expected = [
        {"checkpoint": LABELS[0], "decision": "HOLD", "effects": []},
        {"checkpoint": LABELS[1], "decision": "REFUSE", "effects": []},
        {"checkpoint": LABELS[2], "decision": "COMMIT", "effects": effect},
        {"checkpoint": LABELS[3], "decision": "COMMIT", "effects": effect},
    ]
    for index, (actual, wanted) in enumerate(zip(captured[1:], expected), 1):
        require(actual == wanted,
                f"RUN.jsonl checkpoint {index}: expected {wanted!r}, got {actual!r}")

    command = [sys.executable, "-I", "-B", "checkpoint.py"]
    print("Command: python -I -B checkpoint.py", flush=True)
    result = subprocess.run(command, cwd=destination, capture_output=True, text=True)
    print("Checkpoint output:")
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print("Checkpoint stderr:", result.stderr, sep="\n", end="")
    require(result.returncode == 0, f"checkpoint.py exited {result.returncode}")

    lines = result.stdout.splitlines()
    require(len(lines) == 5, f"checkpoint output: expected 5 lines, got {len(lines)}")
    output = [json.loads(line) for line in lines]
    require(isinstance(output[0], dict), "checkpoint output: invalid header")
    require(output[0].get("request_sha256") == request_hash,
            f"request SHA-256: expected {request_hash}, got {output[0].get('request_sha256')!r}")
    require(output[0].get("sqlite") == sqlite3.sqlite_version,
            f"SQLite version: expected {sqlite3.sqlite_version}, got {output[0].get('sqlite')!r}")
    for index, (actual, wanted) in enumerate(zip(output[1:], expected), 1):
        require(actual == wanted,
                f"checkpoint {index}: expected {wanted!r}, got {actual!r}")


def main():
    print(f"OS: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"SQLite: {sqlite3.sqlite_version}")
    try:
        with tempfile.TemporaryDirectory(prefix="refund-reproduce-") as directory:
            destination = Path(directory)
            extract_archive(destination)
            verify_checksums(destination)
            replay(destination)
    except (Mismatch, OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
