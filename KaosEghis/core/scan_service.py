from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import shutil

from KaosEghis.db.database import get_data_dir


DEFAULT_NAPS2_PROFILE = "Canon DR-C125 Native"
DEFAULT_CLEANUP_INTERVAL_MINUTES = 30
SCAN_OUTPUT_DIR_NAME = "temp"


@dataclass(frozen=True)
class ScanCommand:
    executable: str
    arguments: tuple[str, ...]
    output_path: Path


@dataclass(frozen=True)
class CleanupResult:
    deleted: int
    skipped: int
    failed: int


def get_scan_output_dir(data_dir: Path | None = None) -> Path:
    root = (data_dir or get_data_dir()).expanduser().resolve()
    output_dir = (root / SCAN_OUTPUT_DIR_NAME).resolve()
    if output_dir.parent != root or output_dir.name != SCAN_OUTPUT_DIR_NAME:
        raise ValueError("Unsafe scan output directory.")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def find_naps2_console() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "NAPS2"
        / "NAPS2.Console.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "NAPS2"
        / "NAPS2.Console.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    discovered = shutil.which("NAPS2.Console.exe") or shutil.which("naps2.console")
    return Path(discovered).resolve() if discovered else None


def timestamped_pdf_path(
    output_dir: Path | None = None,
    *,
    now: datetime | None = None,
) -> Path:
    scan_dir = _validated_scan_dir(output_dir)
    timestamp = (now or datetime.now()).strftime("%Y%m%d%H%M")
    output_path = scan_dir / f"{timestamp}.pdf"
    if output_path.exists():
        raise FileExistsError("A scan already exists for the current minute.")
    return output_path


def prepare_scan_command(
    output_dir: Path | None = None,
    *,
    profile: str = DEFAULT_NAPS2_PROFILE,
    now: datetime | None = None,
    executable: Path | None = None,
) -> ScanCommand:
    console = executable or find_naps2_console()
    if console is None or not Path(console).is_file():
        raise FileNotFoundError("NAPS2 Console is not installed.")
    if not profile.strip():
        raise ValueError("NAPS2 scan profile is not configured.")

    output_path = timestamped_pdf_path(output_dir, now=now)
    return ScanCommand(
        executable=str(Path(console).resolve()),
        arguments=("-o", str(output_path), "-p", profile.strip(), "-v"),
        output_path=output_path,
    )


def list_scanned_pdfs(output_dir: Path | None = None) -> list[Path]:
    scan_dir = _validated_scan_dir(output_dir)
    pdfs = [
        path
        for path in scan_dir.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix.casefold() == ".pdf"
    ]
    return sorted(pdfs, key=lambda path: path.stat().st_mtime, reverse=True)


def clean_scan_output_dir(output_dir: Path | None = None) -> CleanupResult:
    scan_dir = _validated_scan_dir(output_dir)
    deleted = 0
    skipped = 0
    failed = 0
    for entry in scan_dir.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            skipped += 1
            continue
        try:
            entry.unlink()
            deleted += 1
        except OSError:
            failed += 1
    return CleanupResult(deleted=deleted, skipped=skipped, failed=failed)


def discard_failed_scan(output_path: Path, output_dir: Path | None = None) -> None:
    scan_dir = _validated_scan_dir(output_dir)
    candidate = output_path.resolve()
    if candidate.parent != scan_dir:
        return
    try:
        if candidate.is_file() or candidate.is_symlink():
            candidate.unlink()
    except OSError:
        pass


def _validated_scan_dir(output_dir: Path | None) -> Path:
    if output_dir is None:
        return get_scan_output_dir()
    scan_dir = Path(output_dir).expanduser().resolve()
    if scan_dir.name != SCAN_OUTPUT_DIR_NAME:
        raise ValueError("Unsafe scan output directory.")
    scan_dir.mkdir(parents=True, exist_ok=True)
    return scan_dir
