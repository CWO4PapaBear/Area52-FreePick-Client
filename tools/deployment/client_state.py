import json
import os
from pathlib import Path
import subprocess
import time


def ensure_closed():
    state_file = os.environ.get('AREA52_CLIENT_STATE_FILE')
    nonce = os.environ.get('AREA52_CLIENT_STATE_NONCE')
    if state_file or nonce:
        if not state_file or not nonce:
            raise RuntimeError('Incomplete Windows client-state probe')
        try:
            state = json.loads(Path(state_file).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as error:
            raise RuntimeError('Windows client-state probe is unavailable') from error
        age = time.time() * 1000 - state.get('checked_at_ms', 0)
        if state.get('nonce') != nonce or not -1000 <= age <= 3000:
            raise RuntimeError('Windows client-state probe is stale or does not match this activation')
        if state.get('closed') is not True:
            raise RuntimeError('Close Ascension before continuing this package')
        return
    try:
        result = subprocess.run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                                 '-NoProfile', '-Command',
                                 'if (Get-Process Ascension -ErrorAction SilentlyContinue) { exit 2 }'],
                                capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError('Run Activate-Area52.ps1 from Windows so client closure can be checked') from error
    if result.returncode:
        raise RuntimeError('Close Ascension before continuing this package')
