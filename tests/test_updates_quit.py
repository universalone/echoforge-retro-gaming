"""Tests selfupdate.py with made-up GitHub answers, and padquit.close_gently on a throwaway process.
Run: python -I tests/test_updates_quit.py"""
import hashlib
import io
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import padquit  # noqa: E402
import selfupdate as U  # noqa: E402

fails = 0


def check(name, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    fails += 0 if ok else 1


DATA = b"zip bytes"
SHA = hashlib.sha256(DATA).hexdigest()


def rel(v, digest=True, draft=False, pre=False, name=None):
    return {"draft": draft, "prerelease": pre, "html_url": f"https://github.com/x/releases/v{v}", "body": "notes",
            "assets": [{"name": name or f"EchoForge-Retro-Gaming-{v}-win64.zip", "size": len(DATA),
                        "browser_download_url": f"https://github.com/x/download/v{v}/EchoForge-Retro-Gaming-{v}-win64.zip",
                        **({"digest": "sha256:" + SHA} if digest else {})}]}


check("2.10.0 is newer than 2.9.0", U.cmp_version("2.10.0", "2.9.0") == 1 and U.cmp_version("v2.4.0", "2.4") == 0)
r = U.check("2.4.0", lambda: [rel("2.4.1"), rel("2.5.0", draft=True), rel("2.6.0", pre=True), rel("2.7.0", digest=False), rel("2.3.2")])
check("offers the newest published release with a checksum", r["ok"] and r["update"] and r["latest"]["version"] == "2.4.1", r.get("latest"))
check("no update when this copy is newest", not U.check("2.4.0", lambda: [rel("2.3.2")])["update"])
check("other files aren't Retro downloads", U.newest([rel("9.9.9", name="EchoForge-Setup-9.9.9.exe")]) is None)
check("an old-style installer isn't offered (Retro ships as a zip now)", U.newest([rel("9.9.9", name="EchoForge-Retro-Gaming-Setup-9.9.9.exe")]) is None)

with tempfile.TemporaryDirectory() as d:
    opener = lambda req, timeout: io.BytesIO(DATA)  # noqa: E731
    got = []
    path = U.download(r["latest"], d, got.append, opener)
    check("downloads and checks the zip", path.read_bytes() == DATA and got[-1] == 100)
    bad = dict(r["latest"], sha256="0" * 64)
    try:
        U.download(bad, d, opener=opener)
        check("refuses a download that doesn't match", False)
    except ValueError:
        check("refuses a download that doesn't match", not (Path(d) / (bad["name"] + ".part")).exists())
    try:
        U.download(dict(r["latest"], url="https://evil.example/x.exe"), d, opener=opener)
        check("only downloads from GitHub", False)
    except ValueError:
        check("only downloads from GitHub", True)

# Unpacking a downloaded zip beside the program, as an update does.
import zipfile  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    good = d / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("app/jl_retro.pyw", "# retro"); z.writestr("app/installed.txt", "9.9.9"); z.writestr("python/pythonw.exe", "exe")
    new = U.unpack(good, d / "Program")
    check("a zip unpacks into _update beside the program", new == d / "Program" / "_update" and (new / "app" / "jl_retro.pyw").exists())
    again = U.unpack(good, d / "Program")
    check("unpacking again starts from a clean _update", again == new and sorted(p.name for p in new.iterdir()) == ["app", "python"])
    part = d / "part.zip"
    with zipfile.ZipFile(part, "w") as z:
        z.writestr("app/readme.txt", "no program")
    try:
        U.unpack(part, d / "Program2")
        check("an incomplete zip is refused", False)
    except ValueError:
        check("an incomplete zip is refused and cleaned up", not (d / "Program2" / "_update").exists())
    evil = d / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../outside.txt", "x"); z.writestr("app/jl_retro.pyw", "x"); z.writestr("python/pythonw.exe", "x")
    try:
        U.unpack(evil, d / "Program3")
        check("a zip with paths leading outside is refused", False)
    except ValueError:
        check("a zip with paths leading outside is refused", not (d / "outside.txt").exists())

# A process with no window can't be asked to close, so it's forced after the wait.
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=subprocess.CREATE_NO_WINDOW)
t = time.time()
how = padquit.close_gently(p.pid, grace=1.5, wait=lambda: p.poll() is not None)
p.wait(5)
check("a game that won't close is forced after the wait", how == "forced" and p.poll() is not None and time.time() - t < 6, how)
check("the controller helper ships next to padquit", padquit.SCRIPT.exists())
print(f"{fails} FAILED" if fails else "ALL PASSED")
sys.exit(1 if fails else 0)
