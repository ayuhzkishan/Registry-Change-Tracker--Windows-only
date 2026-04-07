"""
Real-time registry monitoring engine.

Uses ctypes to call the Win32 API `RegNotifyChangeKeyValue` to block
and wait for registry changes in specific paths.
"""

import ctypes
import winreg
import threading
import time
import json
from datetime import datetime, timezone
from typing import Callable, List, Dict, Any

from rich.console import Console

from regtracker.snapshot import parse_hive_path, take_snapshot, SnapshotResult
from regtracker.diff import compare_snapshots
from regtracker.process_utils import get_recent_processes

console = Console()

# Win32 API Constants
REG_NOTIFY_CHANGE_NAME = 0x00000001        # Changes to names of keys/values
REG_NOTIFY_CHANGE_ATTRIBUTES = 0x00000002  # Changes to attributes
REG_NOTIFY_CHANGE_LAST_SET = 0x00000004    # Changes to values
REG_NOTIFY_CHANGE_SECURITY = 0x00000008    # Changes to security descriptors

ALL_NOTIFY_FLAGS = (
    REG_NOTIFY_CHANGE_NAME | 
    REG_NOTIFY_CHANGE_ATTRIBUTES | 
    REG_NOTIFY_CHANGE_LAST_SET | 
    REG_NOTIFY_CHANGE_SECURITY
)

class RegistryWatcher:
    """Watches multiple registry paths concurrently."""
    
    def __init__(self, paths: List[str]):
        self.paths = paths
        self.running = False
        self.threads: List[threading.Thread] = []
        
    def _watch_path(self, path: str):
        """Worker function for a single path."""
        try:
            hive_handle, subkey, hive_name = parse_hive_path(path)
        except ValueError as e:
            console.print(f"[red]Error parsing path {path}: {e}[/]")
            return
            
        full_path = f"{hive_name}\\{subkey}"
        
        # Take initial in-memory baseline
        try:
            baseline = take_snapshot(path)
        except Exception as e:
            console.print(f"[red]Failed to take initial baseline for {full_path}: {e}[/]")
            return

        with console.status(f"[cyan]Opening handle for {full_path}...[/]"):
            try:
                # Open the key requesting NOTIFY access
                key = winreg.OpenKey(hive_handle, subkey, 0, winreg.KEY_READ | winreg.KEY_NOTIFY)
            except OSError as e:
                console.print(f"[bold red]❌ Cannot monitor {full_path}: {e}[/]")
                return

        console.print(f"[green]👁️  Watching:[/] {full_path}")
        
        while self.running:
            # This call blocks until a change happens.
            # Using ctypes because winreg module in Python doesn't expose it directly.
            # Signature: LONG RegNotifyChangeKeyValue(HKEY, BOOL, DWORD, HANDLE, BOOL)
            try:
                result = ctypes.windll.advapi32.RegNotifyChangeKeyValue(
                    int(key),          # Handle to open key
                    True,              # bWatchSubtree (watch all subkeys)
                    ALL_NOTIFY_FLAGS,  # Conditions to wait for
                    None,              # hEvent (not using event handles)
                    False              # fAsynchronous (False = blocks)
                )
            except Exception as e:
                console.print(f"[red]Watcher error on {full_path}: {e}[/]")
                break
                
            if not self.running:
                break
                
            if result == 0:  # ERROR_SUCCESS
                # Change detected! Take a new snapshot to see what changed
                new_snapshot = take_snapshot(path)
                
                # Diff it
                diff_result = compare_snapshots(
                    "baseline", baseline.entries, 
                    "new", new_snapshot.entries,
                    apply_filters=True
                )
                
                if diff_result.total_changes > 0:
                    self._handle_change(full_path, diff_result)
                    
                # The new snapshot becomes the baseline
                baseline = new_snapshot
                
        winreg.CloseKey(key)

    def _handle_change(self, watched_path: str, diff_result):
        """Process and report a detected change."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Heuristic: Check for recently created processes (last 5 seconds)
        recent_procs = get_recent_processes(5.0)
        suspects = [f"{p.name} (PID: {p.pid})" for p in recent_procs[:3]]
        suspect_str = ", ".join(suspects) if suspects else "Unknown (System/Background)"
        
        log_event = {
            "timestamp": now,
            "watched_path": watched_path,
            "suspect_processes": suspects,
            "changes": []
        }
        
        console.print(f"\n[bold white on red] 🚨 REGISTRY CHANGE DETECTED [/] [dim]{now}[/]")
        console.print(f"  [cyan]Path:[/] {watched_path}")
        console.print(f"  [cyan]Suspects:[/] [yellow]{suspect_str}[/]")
        
        if diff_result.added:
            for (kpath, vname), entry in diff_result.added.items():
                disp = vname if vname else "(Default)"
                console.print(f"  [bold green]🟢 ADDED:[/] {kpath}\\{disp} = {entry.value_data}")
                log_event["changes"].append({"type": "added", "path": f"{kpath}\\{disp}", "value": entry.value_data})
                
        if diff_result.deleted:
            for (kpath, vname), entry in diff_result.deleted.items():
                disp = vname if vname else "(Default)"
                console.print(f"  [bold red]🔴 DELETED:[/] {kpath}\\{disp}")
                log_event["changes"].append({"type": "deleted", "path": f"{kpath}\\{disp}"})
                
        if diff_result.modified:
            for (kpath, vname), (old_e, new_e) in diff_result.modified.items():
                disp = vname if vname else "(Default)"
                console.print(f"  [bold yellow]🟡 MODIFIED:[/] {kpath}\\{disp}")
                console.print(f"    [dim]{old_e.value_data}[/] → [white]{new_e.value_data}[/]")
                log_event["changes"].append({"type": "modified", "path": f"{kpath}\\{disp}", "old": old_e.value_data, "new": new_e.value_data})

        # Append to log file
        try:
            with open("regtracker_monitor.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_event) + "\n")
        except IOError:
            pass

    def start(self):
        """Start monitoring all paths in separate threads."""
        self.running = True
        console.print("\n[bold green]🚀 Starting Registry Monitor[/]")
        console.print("[dim]Press Ctrl+C to stop...[/]\n")
        
        for path in self.paths:
            t = threading.Thread(target=self._watch_path, args=(path,), daemon=True)
            t.start()
            self.threads.append(t)
            time.sleep(0.1) # Stagger starts slightly
            
    def stop(self):
        """Stop all monitoring threads."""
        self.running = False
        console.print("\n[bold yellow]🛑 Stopping monitor...[/]")
