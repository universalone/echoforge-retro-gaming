"""Tests winutil.game_screen (the middle of three screens is where games go) and the RetroArch settings for it.
Run: python -I tests/test_screens.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import winutil  # noqa: E402

fails = 0


def check(name, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    if not ok:
        fails += 1


g = winutil.game_screen
check("NVIDIA Surround (one 5846 x 1080 screen): the middle 1920 x 1080", g([(0, 0, 5846, 1080)]) == (True, (1963, 0, 1920, 1080)), str(g([(0, 0, 5846, 1080)])))
check("three spanned without bezel correction", g([(0, 0, 5760, 1080)]) == (True, (1920, 0, 1920, 1080)))
check("three 1440p monitors spanned", g([(0, 0, 7680, 1440)]) == (True, (2560, 0, 2560, 1440)))
check("three separate monitors: the middle one by position",
      g([(1920, 0, 1920, 1080), (0, 0, 1920, 1080), (3840, 0, 1920, 1080)]) == (True, (1920, 0, 1920, 1080)))
check("three monitors with the main one in the middle at 0,0",
      g([(0, 0, 1920, 1080), (-1920, 0, 1920, 1080), (1920, 0, 1920, 1080)]) == (True, (0, 0, 1920, 1080)))
check("one ordinary screen: fullscreen as before", g([(0, 0, 1920, 1080)])[0] is False)
check("an ultrawide isn't three screens", g([(0, 0, 3440, 1440)])[0] is False)
check("two monitors aren't three", g([(0, 0, 1920, 1080), (1920, 0, 1920, 1080)])[0] is False)
check("two spanned aren't three", g([(0, 0, 3840, 1080)])[0] is False)
check("no screens", g([]) == (False, None))

cfg = winutil.retroarch_game_screen_cfg((1963, 0, 1920, 1080))
check("RetroArch: borderless window on the game screen, no menu bar, settings not saved over retroarch.cfg",
      all(k in cfg for k in ('video_fullscreen = "false"', 'video_window_show_decorations = "false"', 'ui_menubar_enable = "false"',
                              'video_windowed_position_x = "1963"', 'video_windowed_position_width = "1920"',
                              'video_windowed_position_height = "1080"', 'config_save_on_exit = "false"')))

mons = winutil.monitors()
check("this PC's monitors can be read", isinstance(mons, list) and all(len(m) == 4 for m in mons), str(mons))

print(f"{fails} FAILED" if fails else "ALL PASSED")
sys.exit(1 if fails else 0)
