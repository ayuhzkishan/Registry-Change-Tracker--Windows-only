"""
Registry Diff Engine.

Calculates the difference between two snapshots, applying noise
filters to isolate meaningful changes.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Set
from collections import defaultdict

from regtracker.snapshot import RegistryEntry
from regtracker.filters import is_noise


@dataclass
class DiffResult:
    """Container for the diff operation results."""
    snapshot_a_id: str
    snapshot_b_id: str
    
    # Dictionaries mapping (key_path, value_name) -> RegistryEntry (or tuple of entries for modified)
    added: Dict[Tuple[str, str], RegistryEntry] = field(default_factory=dict)
    deleted: Dict[Tuple[str, str], RegistryEntry] = field(default_factory=dict)
    modified: Dict[Tuple[str, str], Tuple[RegistryEntry, RegistryEntry]] = field(default_factory=dict)
    
    filtered_count: int = 0
    
    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.deleted) + len(self.modified)


def _build_entry_map(entries: List[RegistryEntry]) -> Dict[Tuple[str, str], RegistryEntry]:
    """Convert a list of entries into a lookup dictionary using (path, name) as key."""
    return {(e.key_path, e.value_name): e for e in entries}


def compare_snapshots(
    snapshot_a_id: str, 
    entries_a: List[RegistryEntry], 
    snapshot_b_id: str, 
    entries_b: List[RegistryEntry],
    apply_filters: bool = True
) -> DiffResult:
    """
    Compare two sets of registry entries and return added, deleted, and modified items.
    """
    result = DiffResult(snapshot_a_id=snapshot_a_id, snapshot_b_id=snapshot_b_id)
    
    map_a = _build_entry_map(entries_a)
    map_b = _build_entry_map(entries_b)
    
    keys_a = set(map_a.keys())
    keys_b = set(map_b.keys())
    
    # 1. Added: exist in B but not in A
    added_keys = keys_b - keys_a
    for k in added_keys:
        if apply_filters and is_noise(k[0], k[1]):
            result.filtered_count += 1
            continue
        result.added[k] = map_b[k]
            
    # 2. Deleted: exist in A but not in B
    deleted_keys = keys_a - keys_b
    for k in deleted_keys:
        if apply_filters and is_noise(k[0], k[1]):
            result.filtered_count += 1
            continue
        result.deleted[k] = map_a[k]
        
    # 3. Modified: exist in both, but value data or type changed
    common_keys = keys_a.intersection(keys_b)
    for k in common_keys:
        val_a = map_a[k]
        val_b = map_b[k]
        
        # Check if type or serialized data changed
        if val_a.value_type != val_b.value_type or val_a.value_data != val_b.value_data:
            if apply_filters and is_noise(k[0], k[1]):
                result.filtered_count += 1
                continue
            result.modified[k] = (val_a, val_b)
            
    return result
