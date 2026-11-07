# EchoForge Retro Gaming

A Windows game library for [RetroArch](https://www.retroarch.com): browse your games by system and series, see box art and screenshots, and play with a keyboard or controller.

## What it does

- Reads your RetroArch playlists and launches games in RetroArch
- Finds series across systems and shows full-screen game pages
- Backs up your saves after you play, and on a weekly schedule
- Adds game files from a folder you choose, and works out the system from the file itself

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
