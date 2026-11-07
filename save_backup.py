"""Save backups: dated snapshots of RetroArch's saves and save states.

Each snapshot is <root>\\<YYYY-MM-DD HH.MM.SS>\\{saves,states} with a manifest.json.
A backup is skipped when nothing changed since the last one, the newest KEEP are
kept, and older ones go to the Recycle Bin.
"""
import hashlib
import json
import shutil
import time
from pathlib import Path

from winutil import recycle

DEFAULT_ROOT = Path.home() / "EchoForge Backups" / "Retro Gaming"
KEEP = 10
WEEK = 7 * 86400


def sources(ra_dir):
    return [("Saves", Path(ra_dir) / "saves"), ("Save states", Path(ra_dir) / "states")]


def _files(folder):
    if not folder.is_dir():
        return []
    return sorted(f for f in folder.rglob("*") if f.is_file())


def signature(ra_dir):
    h = hashlib.sha1()
    for _, folder in sources(ra_dir):
        for f in _files(folder):
            st = f.stat()
            h.update(f"{f.relative_to(folder.parent)}|{st.st_size}|{int(st.st_mtime)}\n".encode("utf-8"))
    return h.hexdigest()


def snapshots(root):
    root = Path(root)
    out = []
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir(), reverse=True):
        m = d / "manifest.json"
        if d.is_dir() and not d.name.endswith(".partial") and m.is_file():
            try:
                info = json.loads(m.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({"name": d.name, "at": info.get("at", 0), "reason": info.get("reason", ""),
                        "files": info.get("files", 0), "bytes": info.get("bytes", 0), "sig": info.get("sig", "")})
    return out


def run(ra_dir, root, reason, keep=KEEP):
    """Returns {"ok", "skipped"?, "name"?, "files"?, "error"?}."""
    root = Path(root)
    sig = signature(ra_dir)
    existing = snapshots(root)
    if existing and existing[0]["sig"] == sig:
        return {"ok": True, "skipped": True}
    if not any(_files(folder) for _, folder in sources(ra_dir)):
        return {"ok": True, "skipped": True}
    name = time.strftime("%Y-%m-%d %H.%M.%S")
    partial = root / (name + ".partial")
    try:
        files = total = 0
        for _, folder in sources(ra_dir):
            for f in _files(folder):
                dest = partial / f.relative_to(folder.parent)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                if dest.stat().st_size != f.stat().st_size:
                    raise OSError(f"Copy of {f.name} came out the wrong size")
                files += 1
                total += f.stat().st_size
        manifest = {"at": int(time.time()), "reason": reason, "sig": sig, "files": files, "bytes": total,
                    "sources": [{"label": label, "path": str(folder)} for label, folder in sources(ra_dir)]}
        (partial / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        partial.rename(root / name)
    except OSError as e:
        recycle(partial)
        return {"ok": False, "error": str(e)}
    for old in snapshots(root)[keep:]:
        recycle(root / old["name"])
    return {"ok": True, "name": name, "files": files}


def restore(ra_dir, root, name):
    """Copies a snapshot back over the current saves, after backing those up first."""
    snap = Path(root) / name
    if not (snap / "manifest.json").is_file() or snap.parent != Path(root):
        return {"ok": False, "error": "That backup wasn't found."}
    safety = run(ra_dir, root, "before restore", keep=KEEP + 1)
    if not safety["ok"]:
        return {"ok": False, "error": "Couldn't back up your current saves first: " + safety.get("error", "")}
    count = 0
    for _, folder in sources(ra_dir):
        src = snap / folder.name
        for f in _files(src):
            dest = folder / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            count += 1
    return {"ok": True, "files": count}
