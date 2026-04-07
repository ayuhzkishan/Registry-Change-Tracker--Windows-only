"""
Configuration and constants for the Registry Change Tracker.
"""

import os
import winreg

# ---------------------------------------------------------------------------
# Hive name → winreg constant mapping
# ---------------------------------------------------------------------------
HIVE_MAP: dict[str, int] = {
    "HKCU":                winreg.HKEY_CURRENT_USER,
    "HKEY_CURRENT_USER":   winreg.HKEY_CURRENT_USER,
    "HKLM":                winreg.HKEY_LOCAL_MACHINE,
    "HKEY_LOCAL_MACHINE":  winreg.HKEY_LOCAL_MACHINE,
    "HKU":                 winreg.HKEY_USERS,
    "HKEY_USERS":          winreg.HKEY_USERS,
    "HKCR":                winreg.HKEY_CLASSES_ROOT,
    "HKEY_CLASSES_ROOT":   winreg.HKEY_CLASSES_ROOT,
    "HKCC":                winreg.HKEY_CURRENT_CONFIG,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

# Friendly short names for display
HIVE_SHORT_NAMES: dict[int, str] = {
    winreg.HKEY_CURRENT_USER:   "HKCU",
    winreg.HKEY_LOCAL_MACHINE:  "HKLM",
    winreg.HKEY_USERS:          "HKU",
    winreg.HKEY_CLASSES_ROOT:   "HKCR",
    winreg.HKEY_CURRENT_CONFIG: "HKCC",
}

# ---------------------------------------------------------------------------
# Registry value type → human-readable name mapping
# ---------------------------------------------------------------------------
VALUE_TYPE_NAMES: dict[int, str] = {
    winreg.REG_NONE:                "REG_NONE",
    winreg.REG_SZ:                  "REG_SZ",
    winreg.REG_EXPAND_SZ:           "REG_EXPAND_SZ",
    winreg.REG_BINARY:              "REG_BINARY",
    winreg.REG_DWORD:               "REG_DWORD",
    winreg.REG_DWORD_BIG_ENDIAN:    "REG_DWORD_BIG_ENDIAN",
    winreg.REG_LINK:                "REG_LINK",
    winreg.REG_MULTI_SZ:            "REG_MULTI_SZ",
    winreg.REG_RESOURCE_LIST:       "REG_RESOURCE_LIST",
    winreg.REG_FULL_RESOURCE_DESCRIPTOR: "REG_FULL_RESOURCE_DESCRIPTOR",
    winreg.REG_RESOURCE_REQUIREMENTS_LIST: "REG_RESOURCE_REQUIREMENTS_LIST",
    winreg.REG_QWORD:               "REG_QWORD",
}

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DEFAULT_DB_DIR = os.path.join(os.path.expanduser("~"), ".regtracker")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "regtracker.db")

# ---------------------------------------------------------------------------
# Snapshot defaults
# ---------------------------------------------------------------------------
MAX_VALUE_DATA_LENGTH = 4096  # Truncate binary blobs larger than this (bytes)
