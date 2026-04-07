"""
Rollback Script Generator.

Generates Windows Registry Editor Version 5.00 (`.reg`) files
that undo the changes found in a DiffResult.
"""

from typing import TextIO
import winreg
from regtracker.diff import DiffResult

def _escape_reg_string(text: str) -> str:
    """Escapes strings for .reg files."""
    return text.replace("\\\\", "\\\\\\\\").replace('"', '\\\\"')

def _format_value_for_reg(value_type: int, value_data: str) -> str:
    """
    Format a value into .reg syntax.
    Note: Stored blobs are base64 encoded by our engine, so reversing
    binary blobs back into pure hex isn't fully implemented in this MVP.
    We handle strings & dwords smoothly.
    """
    if value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return f'"{_escape_reg_string(value_data)}"'
    if value_type == winreg.REG_DWORD:
        try:
            return f'dword:{int(value_data):08x}'
        except ValueError:
            return f'"{_escape_reg_string(value_data)}"'
    # Fallback for others (treated as string/unsupported for direct .reg MVP)
    return f'"{_escape_reg_string(value_data)}"'

def generate_rollback(diff: DiffResult, file: TextIO):
    """
    Generates a .reg rollback script.
    - If a key was ADDED, the rollback DELETES it.
    - If a key was DELETED, the rollback ADDS it back.
    - If a key was MODIFIED, the rollback RESTORES the old value.
    """
    lines = [
        "Windows Registry Editor Version 5.00",
        "",
        "; ==================================================================",
        "; Registry Tracker Rollback Script",
        f"; Targets Diff: {diff.snapshot_a_id} -> {diff.snapshot_b_id}",
        "; WARNING: REVIEW BEFORE EXECUTING",
        "; ==================================================================",
        ""
    ]
    
    # 1. Reverse Additions (Delete the added keys/values)
    if diff.added:
        lines.append("; --- Reversing Additions ---")
        for (kpath, vname), entry in sorted(diff.added.items()):
            if vname == "":  # Default value
                lines.append(f"[{kpath}]")
                lines.append('@=-')
            else:
                lines.append(f"[{kpath}]")
                lines.append(f'"{_escape_reg_string(vname)}"=-')
            lines.append("")

    # 2. Reverse Deletions (Add them back)
    if diff.deleted:
        lines.append("; --- Reversing Deletions (Restoring original values) ---")
        for (kpath, vname), entry in sorted(diff.deleted.items()):
            lines.append(f"[{kpath}]")
            val_str = _format_value_for_reg(entry.value_type, entry.value_data)
            if vname == "":
                lines.append(f"@={val_str}")
            else:
                lines.append(f'"{_escape_reg_string(vname)}"={val_str}')
            lines.append("")

    # 3. Reverse Modifications (Restore old values)
    if diff.modified:
        lines.append("; --- Reversing Modifications (Restoring old values) ---")
        for (kpath, vname), (old_e, new_e) in sorted(diff.modified.items()):
            lines.append(f"[{kpath}]")
            val_str = _format_value_for_reg(old_e.value_type, old_e.value_data)
            if vname == "":
                lines.append(f"@={val_str}")
            else:
                lines.append(f'"{_escape_reg_string(vname)}"={val_str}')
            lines.append("")

    file.write("\\n".join(lines) + "\\n")
