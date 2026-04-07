"""
Registry snapshot engine.

Recursively walks a specified registry hive/path and collects all
keys and their values into a flat list of RegistryEntry records.
"""

from __future__ import annotations

import base64
import winreg
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from regtracker.config import HIVE_MAP, VALUE_TYPE_NAMES, MAX_VALUE_DATA_LENGTH

console = Console()


@dataclass
class RegistryEntry:
    """A single registry value within a key."""
    key_path: str       # Full path, e.g. "HKCU\\Software\\Microsoft\\Windows"
    value_name: str     # Value name ("" for the default value)
    value_type: int     # winreg type constant (REG_SZ, REG_DWORD, etc.)
    value_data: str     # Serialised value data (string representation)


@dataclass
class SnapshotResult:
    """Container for the results of a registry scan."""
    hive_name: str                     # Short hive name, e.g. "HKCU"
    root_path: str                     # Subkey path the user specified
    entries: list[RegistryEntry] = field(default_factory=list)
    keys_scanned: int = 0
    keys_denied: int = 0
    errors: list[str] = field(default_factory=list)


def parse_hive_path(hive_path: str) -> tuple[int, str, str]:
    """
    Parse a user-supplied hive path like 'HKCU\\Software\\Microsoft'
    into (hive_handle, subkey_path, hive_short_name).

    Returns:
        Tuple of (winreg hive constant, subkey path, hive short name).

    Raises:
        ValueError: If the hive name is not recognised.
    """
    # Normalise separators
    hive_path = hive_path.replace("/", "\\")

    parts = hive_path.split("\\", 1)
    hive_name = parts[0].upper()
    subkey = parts[1] if len(parts) > 1 else ""

    if hive_name not in HIVE_MAP:
        raise ValueError(
            f"Unknown registry hive: '{hive_name}'. "
            f"Valid hives: {', '.join(sorted(set(HIVE_MAP.keys())))}"
        )

    return HIVE_MAP[hive_name], subkey, hive_name


def _serialize_value_data(data, value_type: int) -> str:
    """Convert a registry value to a string for storage."""
    if data is None:
        return ""

    if value_type == winreg.REG_BINARY:
        if isinstance(data, bytes):
            if len(data) > MAX_VALUE_DATA_LENGTH:
                data = data[:MAX_VALUE_DATA_LENGTH]
            return base64.b64encode(data).decode("ascii")
        return str(data)

    if value_type == winreg.REG_MULTI_SZ:
        if isinstance(data, list):
            return "\\0".join(str(item) for item in data)
        return str(data)

    if value_type in (winreg.REG_DWORD, winreg.REG_QWORD):
        return str(data)

    # REG_SZ, REG_EXPAND_SZ, and others
    return str(data)


def _read_key_values(
    hive_handle: int,
    subkey: str,
    full_path: str,
) -> list[RegistryEntry]:
    """Read all values from a single registry key."""
    entries: list[RegistryEntry] = []
    try:
        key = winreg.OpenKey(hive_handle, subkey, 0, winreg.KEY_READ)
    except PermissionError:
        return entries
    except OSError:
        return entries

    try:
        index = 0
        while True:
            try:
                name, data, val_type = winreg.EnumValue(key, index)
                serialized = _serialize_value_data(data, val_type)
                entries.append(RegistryEntry(
                    key_path=full_path,
                    value_name=name if name else "(Default)",
                    value_type=val_type,
                    value_data=serialized,
                ))
                index += 1
            except OSError:
                break
    finally:
        winreg.CloseKey(key)

    return entries


def _count_subkeys(hive_handle: int, subkey: str) -> Optional[int]:
    """Try to count total subkeys for progress estimation. Returns None on failure."""
    try:
        key = winreg.OpenKey(hive_handle, subkey, 0, winreg.KEY_READ)
        info = winreg.QueryInfoKey(key)
        count = info[0]  # Number of immediate subkeys
        winreg.CloseKey(key)
        return count
    except (PermissionError, OSError):
        return None


def _walk_registry(
    hive_handle: int,
    subkey: str,
    hive_name: str,
    result: SnapshotResult,
    progress: Progress,
    task_id,
):
    """Recursively walk a registry key and collect all values."""
    if subkey:
        full_path = f"{hive_name}\\{subkey}"
    else:
        full_path = hive_name

    # Read values from the current key
    entries = _read_key_values(hive_handle, subkey, full_path)
    result.entries.extend(entries)
    result.keys_scanned += 1

    progress.update(task_id, advance=1, description=f"[cyan]Scanning:[/] ...\\{subkey.rsplit(chr(92), 1)[-1] if subkey else hive_name}")

    # Enumerate subkeys and recurse
    try:
        key = winreg.OpenKey(hive_handle, subkey, 0, winreg.KEY_READ)
    except PermissionError:
        result.keys_denied += 1
        return
    except OSError as e:
        result.errors.append(f"Cannot open {full_path}: {e}")
        return

    try:
        index = 0
        while True:
            try:
                child_name = winreg.EnumKey(key, index)
                child_subkey = f"{subkey}\\{child_name}" if subkey else child_name
                _walk_registry(
                    hive_handle, child_subkey, hive_name, result, progress, task_id
                )
                index += 1
            except PermissionError:
                result.keys_denied += 1
                index += 1
            except OSError:
                break
    finally:
        winreg.CloseKey(key)


def take_snapshot(hive_path: str) -> SnapshotResult:
    """
    Take a snapshot of the specified registry hive/path.

    Args:
        hive_path: A path like 'HKCU\\Software' or 'HKLM\\SYSTEM\\CurrentControlSet'.

    Returns:
        SnapshotResult containing all discovered entries and scan statistics.
    """
    hive_handle, subkey, hive_name = parse_hive_path(hive_path)

    result = SnapshotResult(hive_name=hive_name, root_path=subkey)

    # Try to get a rough count for the progress bar
    estimated_keys = _count_subkeys(hive_handle, subkey)

    console.print(f"\n[bold blue]📸 Starting snapshot of[/] [yellow]{hive_name}\\{subkey}[/]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        # Use estimated count if available, otherwise indeterminate
        total = estimated_keys if estimated_keys else None
        task_id = progress.add_task("[cyan]Scanning...", total=total)

        _walk_registry(hive_handle, subkey, hive_name, result, progress, task_id)

    return result
