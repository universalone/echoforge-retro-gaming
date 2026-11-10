"""Select + Start while a game runs: a tap opens RetroArch's own Quick Menu (save states, screenshots and more),
holding for 2 seconds closes the game and comes back to the dashboard.

padwatch.ps1 reads the controllers (Xbox-style through XInput, PS4 and PS5 controllers through their HID reports,
shared, so RetroArch still gets every button). It never talks to the network or changes settings.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "padwatch.ps1"
MENU_KEY = "F1"  # RetroArch's default menu key (input_menu_toggle)


def close_gently(pid, grace=10.0, wait=None):
    """Asks RetroArch to close like its window's X button, so it writes saves; forces it only if it doesn't go.
    wait: a function that returns True once the process has ended."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # RetroArch asks "press again to quit" (its quit_press_twice setting), so the close request is sent twice.
    for _ in range(2):
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, creationflags=flags)
        if wait and wait():
            return "closed"
        time.sleep(0.6)
    end = time.time() + grace
    while time.time() < end:
        if wait and wait():
            return "closed"
        time.sleep(0.25)
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=flags)
    return "forced"


class Watcher:
    """Runs padwatch.ps1 for one game. on_quit and on_menu are called from a background thread."""

    def __init__(self, pid, on_quit=None, on_menu=None, hold_ms=2000):
        self.pid, self.on_quit, self.on_menu = pid, on_quit, on_menu
        self.lines = []
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
             "-HoldMs", str(int(hold_ms))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            creationflags=flags)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            self.lines.append(line)
            del self.lines[:-50]
            try:
                if line == "quit" and self.on_quit:
                    self.on_quit()
                elif line == "menu" and self.on_menu:
                    self.on_menu()
            except Exception:  # a handler failing must not stop the watcher
                pass

    def send(self, line):
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def open_menu(self):
        """Brings RetroArch forward and presses its menu key there."""
        self.send(f"key {self.pid} {MENU_KEY}")

    def stop(self):
        try:
            self.proc.stdin.close()  # padwatch ends when its input closes
        except OSError:
            pass
        try:
            self.proc.wait(3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
