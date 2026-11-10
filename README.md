# EchoForge Retro Gaming

A Windows game library for [RetroArch](https://www.retroarch.com): browse your games by system and series, see box art and screenshots, and play with a keyboard or controller.

## What it does

- Reads your RetroArch playlists and launches games in RetroArch
- Finds series across systems and shows full-screen game pages
- Backs up your saves after you play, and on a weekly schedule
- Adds game files from a folder you choose, and works out the system from the file itself
- **Skins** (Settings → Skin): built-in looks, skins made from any game's cover (colors from the art, the cover as wallpaper), Surprise me, and a customizer for every color, the heading and body fonts, corners, borders and the CRT scanlines. Uses EchoForge's skin format (`web/skins.js`).
- **Home dashboards** (Settings → Home dashboard): Classic, Couch, Collector, Minimal and Discover, or your own: turn sections on or off, reorder them, choose the cover size, pair a skin, and check it in Preview. Pin to Home on any game.
- **Synopses** (`synopsis.py`): each game page shows the first paragraph or two of the game's Wikipedia article, with year, genre, developer and publisher from Wikidata and a From Wikipedia link (CC BY-SA). Only the game's name is sent. A match needs a game article with the same name; when an original and a remake share it, the one that mentions the system wins, then the oldest. You can write your own, look it up again, or mark a match as the wrong game.
- **Quit and menu from the controller** (`padquit.py`, `padwatch.ps1`): during a game, tap Select + Start for RetroArch's Quick Menu, or hold them for 2 seconds to close the game the same way as its window's close button, so RetroArch saves first. It's forced only if RetroArch doesn't close within 10 seconds.
- **Updates itself** (`selfupdate.py`): once a day the installed app checks this project's GitHub releases and offers Update now. The installer is checked against GitHub's SHA-256 before it runs.

If RetroArch isn't installed, the app offers its official installer. Box art and screenshots come from the libretro thumbnails library, can be turned off in Settings and aren't included here.

## Run or build

Run from source with Python 3.12 on Windows:

    pythonw jl_retro.pyw

Build the installer, which needs NSIS:

    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1

## License

GPL-3.0-or-later. See [LICENSE](LICENSE). Press Start 2P is under the SIL Open Font License, see [web/OFL.txt](web/OFL.txt).

## Legal

EchoForge Retro Gaming contains no games, firmware, BIOS files or keys, doesn't download them and doesn't decrypt or bypass copy protection. Use only games and system files you made yourself from discs, cartridges and hardware you own, where your local law allows it. EchoForge Retro Gaming isn't affiliated with or endorsed by Sony, Microsoft, Nintendo or Sega; their names appear only to describe compatibility. Emulators are separate projects under their own licenses.
