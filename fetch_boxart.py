"""Downloads box art, screenshots and title screens from thumbnails.libretro.com.

Art is saved where RetroArch looks for it, so RetroArch's own menus show it too.
Run again any time you add games; existing art is kept. Pass --all to also get
screenshots and title screens (the launcher does that by itself in the background).
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_fetch  # noqa: E402

spec = importlib.util.spec_from_file_location("jl_retro", Path(__file__).with_name("jl_retro.pyw"))
jl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jl)


def main():
    kinds = art_fetch.KINDS if "--all" in sys.argv else ("Named_Boxarts",)
    games = jl.load_games()
    for kind in kinds:
        got, missing, kept = 0, [], 0
        for g in games:
            dest = jl.thumb_path(g["playlist"], g["label"], kind)
            if dest.exists():
                kept += 1
                continue
            try:
                name = art_fetch.download(g, kind, dest)
                if name:
                    got += 1
                    print(f"OK   {g['title']}  <-  {name}")
                else:
                    missing.append(g["title"])
            except OSError as e:
                missing.append(g["title"])
                print(f"ERR  {g['title']}: {e}", file=sys.stderr)
        print(f"\n{kind}: downloaded {got}, already had {kept}, no match for {len(missing)}")
        for t in missing:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
