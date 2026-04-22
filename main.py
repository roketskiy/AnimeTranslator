from __future__ import annotations

import logging
import sys

# Enable ANSI colors on Windows legacy consoles
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(handle, mode)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main():
    if len(sys.argv) > 1:
        from core_cli import cli
        cli()
    else:
        from ui.app import AnimeTranslatorApp
        app = AnimeTranslatorApp()
        app.run()


if __name__ == "__main__":
    main()
