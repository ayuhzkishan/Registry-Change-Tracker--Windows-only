"""
Process utilities for attributing registry changes.

Windows does not natively expose exactly which process wrote to a registry
key without deep Event Tracing (ETW) hooks or kernel drivers.
This module uses a timing-based heuristic to find processes that were created
around the time of a registry change, or simply dumps contextual processes.
"""

import time
import psutil
from dataclasses import dataclass
from typing import List


@dataclass
class ProcessContext:
    pid: int
    name: str
    username: str
    age_seconds: float


def get_recent_processes(age_threshold_seconds: float = 10.0) -> List[ProcessContext]:
    """
    Returns a list of processes that were created recently.
    This helps identify short-lived installers or malware that just launched
    and modified the registry.
    """
    recent = []
    now = time.time()
    
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'username']):
        try:
            # Sometime processes block access to their info
            info = proc.info
            create_time = info.get('create_time')
            
            if not create_time:
                continue
                
            age = now - create_time
            if 0 <= age <= age_threshold_seconds:
                recent.append(ProcessContext(
                    pid=info['pid'],
                    name=info['name'] or "Unknown",
                    username=info['username'] or "Unknown",
                    age_seconds=round(age, 2)
                ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Sort by youngest first
    recent.sort(key=lambda p: p.age_seconds)
    return recent
