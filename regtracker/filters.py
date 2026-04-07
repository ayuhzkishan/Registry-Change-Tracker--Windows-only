"""
Noise filtering for registry paths.

Windows constantly updates certain registry keys (like MRU lists,
window positions, and caches). This module provides configurable
filters to ignore these noisy paths during a diff.
"""

import re
from typing import List

# Pre-compiled list of common noisy registry paths
DEFAULT_NOISE_PATTERNS = [
    # General caches
    r".*\\MuiCache.*",
    r".*\\UserAssist\\.*",
    r".*\\RecentDocs\\.*",
    
    # Explorer window state/positions
    r".*\\BagMRU.*",
    r".*\\Bags.*",
    r".*\\Explorer\\ComDlg32\\.*",
    r".*\\Explorer\\SessionInfo.*",
    r".*\\Explorer\\TypedPaths.*",
    
    # RunMRU (Windows Run dialog history)
    r".*\\Explorer\\RunMRU.*",
    
    # Crypto/Security caches that rotate fast
    r".*\\Crypto\\RSA\\.*",
    r".*\\SystemCertificates\\.*\\Cache.*",
    
    # Tracing / Diagnostics
    r".*\\Tracing\\.*",
    r".*\\Diagnostics\\.*",
    
    # Service state (changes on every boot)
    r".*\\Services\\.*\\Enum.*",
    
    # Device setup state
    r".*\\DeviceClasses\\.*",
]

_COMPILED_FILTERS: List[re.Pattern] = []

def _compile_filters(patterns: List[str] = None) -> List[re.Pattern]:
    """Compile a list of string patterns into regex objects."""
    if patterns is None:
        patterns = DEFAULT_NOISE_PATTERNS
        
    return [re.compile(p, re.IGNORECASE) for p in patterns]

def get_compiled_filters() -> List[re.Pattern]:
    """Lazy load compiled filters."""
    global _COMPILED_FILTERS
    if not _COMPILED_FILTERS:
        _COMPILED_FILTERS = _compile_filters()
    return _COMPILED_FILTERS

def is_noise(key_path: str, value_name: str = "") -> bool:
    """
    Check if a keypath (or keypath+value combo) matches a noise filter.
    
    Args:
        key_path: The full registry key path
        value_name: Optional value name (sometimes noise is at value level)
        
    Returns:
        True if it should be filtered out, False otherwise.
    """
    full_path = f"{key_path}\\{value_name}" if value_name else key_path
    
    filters = get_compiled_filters()
    for f in filters:
        if f.match(full_path):
            return True
            
    return False
