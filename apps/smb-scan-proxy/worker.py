#!/usr/bin/env python3
from __future__ import annotations

import errno
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

INBOX = Path(os.getenv("INBOX_DIR", "/srv/smb-scan-proxy/inbox"))
QUEUE = Path(os.getenv("QUEUE_DIR", "/var/lib/smb-scan-proxy/queue"))
CREDS = Path("/etc/smb-scan-proxy.backend")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "2"))
STABLE_SECONDS = float(os.getenv("STABLE_SECONDS", "4"))
RETRY_SECONDS = float(os.getenv("UPLOAD_RETRY_SECONDS", "15"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("smb-scan-proxy")

observed: dict[str, tuple[int, int, float]] = {}


def safe_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return clean[:160] or "scan.bin"


def backend_ready() -> bool:
    return all(
        [
            os.getenv("BACKEND_HOST", "").strip(),
            os.getenv("BACKEND_SHARE", "").strip(),
            os.getenv("BACKEND_USER", "").strip(),
            os.getenv("BACKEND_PASSWORD", ""),
            CREDS.exists(),
        ]
    )


def move_to_queue(source: Path, destination: Path) -> None:
    """Move a completed scan into the queue.

    A Proxmox/LXC installation may place /srv and /var/lib on different
    filesystems. os.replace() cannot cross filesystem boundaries, so fall
    back to copy -> atomic rename inside the queue -> unlink source.
    """
    try:
        source.replace(destination)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    temporary = destination.with_name(f".{destination.name}.copying")
    try:
        shutil.copy2(source, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        source.unlink()
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def enqueue_stable_files() -> None:
    now = time.time()
    current: set[str] = set()

    for path in INBOX.iterdir():
        if not path.is_file() or path.is_symlink():
            continue

        current.add(path.name)
        stat = path.stat()
        if stat.st_size <= 0:
            observed[path.name] = (stat.st_size, stat.st_mtime_ns, now)
            continue

        previous = observed.get(path.name)
        signature = (stat.st_size, stat.st_mtime_ns)

        if previous is None or previous[:2] != signature:
            observed[path.name] = (stat.st_size, stat.st_mtime_ns, now)
            continue

        unchanged_since = previous[2]
        if now - unchanged_since < STABLE_SECONDS:
            continue

        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = QUEUE / f"{stamp}-{time.time_ns() % 1000000:06d}-{safe_name(path.name)}"
        try:
            move_to_queue(path, destination)
            log.info("Queued scan %s -> %s", path.name, destination.name)
            observed.pop(path.name, None)
        except FileNotFoundError:
            observed.pop(path.name, None)

    for missing in set(observed) - current:
        observed.pop(missing, None)


def upload(path: Path) -> bool:
    host = os.environ["BACKEND_HOST"].strip()
    share = os.environ["BACKEND_SHARE"].strip()
    subdir = os.getenv("BACKEND_SUBDIR", "").strip().strip("/\\")
    protocol = os.getenv("BACKEND_PROTOCOL", "SMB3").strip() or "SMB3"

    remote_name = safe_name(path.name)
    temp_name = f"{remote_name}.partial"

    command = [
        "smbclient",
        f"//{host}/{share}",
        "-A",
        str(CREDS),
        "-m",
        protocol,
    ]
    if subdir:
        command.extend(["-D", subdir])

    command.extend(
        [
            "-c",
            f'put "{path}" "{temp_name}"; rename "{temp_name}" "{remote_name}"',
        ]
    )

    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )

    if result.returncode == 0:
        log.info("Uploaded %s to //%s/%s%s", path.name, host, share, f"/{subdir}" if subdir else "")
        path.unlink(missing_ok=True)
        return True

    output = result.stdout.strip().replace("\n", " | ")
    log.warning("Upload failed for %s (rc=%s): %s", path.name, result.returncode, output)
    return False


def process_queue() -> bool:
    if not backend_ready():
        return True

    for path in sorted(QUEUE.iterdir(), key=lambda item: item.stat().st_mtime):
        if not path.is_file() or path.is_symlink():
            continue
        if not upload(path):
            return False
    return True


def main() -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    QUEUE.mkdir(parents=True, exist_ok=True)
    log.info("Worker started; inbox=%s queue=%s", INBOX, QUEUE)

    warned_backend = False
    while True:
        try:
            enqueue_stable_files()

            if backend_ready():
                warned_backend = False
                upload_ok = process_queue()
                delay = POLL_SECONDS if upload_ok else RETRY_SECONDS
            else:
                if not warned_backend:
                    log.warning("Backend is not configured yet; received scans will remain queued")
                    warned_backend = True
                delay = min(RETRY_SECONDS, 30)

            time.sleep(delay)
        except Exception:
            log.exception("Worker loop failed")
            time.sleep(RETRY_SECONDS)


if __name__ == "__main__":
    main()
