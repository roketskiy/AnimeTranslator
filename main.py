from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import sys
import unicodedata
from pathlib import Path

import questionary
from questionary import Style
import config
from utils.progress import FancyProgressBar
from core.subtitle_parser import parse_subtitle_file, Subtitle
from core.translator import translate_batch
from core.srt_generator import generate_srt, generate_bilingual_srt, generate_original_srt

if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value |= 0x0004
        kernel32.SetConsoleMode(handle, mode)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

_COLOR = "\033[38;2;212;64;32m"
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _display_width(s: str) -> int:
    w = 0
    for ch in s:
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def _cjk_center(s: str, width: int, fillchar: str = " ") -> str:
    dw = _display_width(s)
    if dw >= width:
        return s
    padding = width - dw
    left = padding // 2
    right = padding - left
    return fillchar * left + s + fillchar * right


def _generate_big_text(text: str) -> list[str]:
    letters_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ASCII-letter-printer-master",
        "Big_letters",
        "letters.py",
    )
    spec = importlib.util.spec_from_file_location("letters", letters_path)
    if spec is None or spec.loader is None:
        return [text]
    letters_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(letters_mod)
    out = letters_mod.OUTPUT("", "", "", "", "", "")
    for ch in text:
        ascii_val = ord(ch)
        if ascii_val >= 97:
            ascii_val -= 32
        out.add_letter(ascii_val)
    lines = out.print_letters().rstrip("\n").split("\n")
    max_width = max(len(line) for line in lines) if lines else 0
    return [line.ljust(max_width) for line in lines]


_BANNER_LINES: list[str] | None = None


def _get_banner_lines() -> list[str]:
    global _BANNER_LINES
    if _BANNER_LINES is None:
        anime = _generate_big_text("ANIME")
        trans = _generate_big_text("TRANS")
        _BANNER_LINES = anime + [""] + trans
    return _BANNER_LINES


_Q_STYLE = Style([
    ("selected", "fg:#d44020"),
])


def _clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _read_key():
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\xe0", b"\x00"):
            ch2 = msvcrt.getch()
            if ch2 == b"H":
                return "up"
            elif ch2 == b"P":
                return "down"
            return None
        elif ch == b"\r":
            return "enter"
        elif ch in (b"q", b"Q"):
            return "q"
        elif ch == b"\x03":
            raise KeyboardInterrupt
        elif ch in (b"j", b"J"):
            return "down"
        elif ch in (b"k", b"K"):
            return "up"
        return None
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "up"
                elif seq == "[B":
                    return "down"
                return None
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch in ("q", "Q"):
                return "q"
            elif ch in ("j", "J"):
                return "down"
            elif ch in ("k", "K"):
                return "up"
            elif ch == "\x03":
                raise KeyboardInterrupt
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return None


class TerminalUI:
    _SEP_THIN = "\u2500"
    _SEP_DOUBLE = "\u2550"
    _ARROW = "\u25b6"

    def __init__(self, modes):
        self.modes = modes
        self.selected = 0
        self.banner_lines = _get_banner_lines()
        self.n_options = len(modes) + 1

        self._title_height = 0
        self._opts_start = 0
        self._opts_end = 0
        self._hint_row = 0

    def draw(self):
        _clear_screen()
        tw = shutil.get_terminal_size().columns
        row = 1

        for line in self.banner_lines:
            sys.stdout.write(f"{_COLOR}{_cjk_center(line, tw)}{_RESET}\n")
        row += len(self.banner_lines)

        sys.stdout.write(f"{_COLOR}{self._SEP_THIN * tw}{_RESET}\n")
        row += 1
        sys.stdout.write("\n")
        row += 1

        self._opts_start = row
        options = [label for label, _ in self.modes] + ["\u9000\u51fa"]
        for i, label in enumerate(options):
            if i == self.selected:
                text = f"  {self._ARROW} {label}"
                sys.stdout.write(f"{_COLOR}{_BOLD}{_cjk_center(text, tw)}{_RESET}\n")
            else:
                text = f"    {label}"
                sys.stdout.write(f"{_DIM}{_cjk_center(text, tw)}{_RESET}\n")
            row += 1
        self._opts_end = row - 1

        sys.stdout.write("\n")
        row += 1
        sys.stdout.write(f"{_COLOR}{self._SEP_THIN * tw}{_RESET}\n")
        row += 1

        self._hint_row = row
        hint = "\u2191\u2193 \u9009\u62e9  \u00b7  Enter \u786e\u8ba4  \u00b7  Q \u9000\u51fa"
        sys.stdout.write(f"{_cjk_center(hint, tw)}\n")
        row += 1

        self._title_height = len(self.banner_lines) + 2

        sys.stdout.write(f"{_COLOR}{self._SEP_DOUBLE * tw}{_RESET}\n")
        row += 1

        sys.stdout.flush()

    def _redraw_opts(self):
        tw = shutil.get_terminal_size().columns
        options = [label for label, _ in self.modes] + ["\u9000\u51fa"]
        for i, label in enumerate(options):
            r = self._opts_start + i
            sys.stdout.write(f"\033[{r};1H\033[2K")
            if i == self.selected:
                text = f"  {self._ARROW} {label}"
                sys.stdout.write(f"{_COLOR}{_BOLD}{_cjk_center(text, tw)}{_RESET}")
            else:
                text = f"    {label}"
                sys.stdout.write(f"{_DIM}{_cjk_center(text, tw)}{_RESET}")
        sys.stdout.flush()

    def enter_progress(self):
        r = self._hint_row + 2
        h = shutil.get_terminal_size().lines
        for i in range(max(0, h - r + 1)):
            sys.stdout.write(f"\033[{r + i};1H\033[2K")
        sys.stdout.write(f"\033[{r};1H")
        sys.stdout.flush()

    def run(self):
        self.draw()
        while True:
            try:
                key = _read_key()
            except KeyboardInterrupt:
                _clear_screen()
                print("  \u518d\u89c1!")
                return

            if key == "up":
                self.selected = (self.selected - 1) % self.n_options
                self._redraw_opts()
            elif key == "down":
                self.selected = (self.selected + 1) % self.n_options
                self._redraw_opts()
            elif key == "enter":
                if self.selected == len(self.modes):
                    _clear_screen()
                    print("  \u518d\u89c1!")
                    return
                self.enter_progress()
                try:
                    self.modes[self.selected][1]()
                except Exception as e:
                    print(f"\n  [\u9519\u8bef] {e}")
                    log.exception("Error in mode %s", self.modes[self.selected][0])
                input("\n  \u6309 Enter \u952e\u7ee7\u7eed...")
                self.draw()
            elif key == "q":
                _clear_screen()
                print("  \u518d\u89c1!")
                return

    def run_text(self):
        while True:
            tw = shutil.get_terminal_size().columns
            print()
            print(_cjk_center("\u2500\u2500 \u8bf7\u9009\u62e9\u6a21\u5f0f \u2500\u2500", tw))
            for i, (label, _) in enumerate(self.modes, 1):
                print(_cjk_center(f"  {i}. {label}", tw))
            print(_cjk_center("  0. \u9000\u51fa", tw))
            try:
                choice = input("\n\u8bf7\u8f93\u5165\u7f16\u53f7: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  \u518d\u89c1!")
                break

            if choice == "0":
                print("  \u518d\u89c1!")
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(self.modes):
                    print()
                    try:
                        self.modes[idx][1]()
                    except Exception as e:
                        print(f"\n  [\u9519\u8bef] {e}")
                        log.exception("Error in mode %s", self.modes[idx][0])
                else:
                    print("  \u65e0\u6548\u9009\u62e9")
            except ValueError:
                print("  \u8bf7\u8f93\u5165\u6709\u6548\u6570\u5b57")


def prompt_choice(prompt: str, options: list[str]) -> int | None:
    if not sys.stdin.isatty():
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            try:
                val = input(f"{prompt} ").strip()
                if not val:
                    return None
                idx = int(val) - 1
                if 0 <= idx < len(options):
                    return idx
            except (ValueError, EOFError):
                pass
            print(f"  \u8bf7\u8f93\u5165 1-{len(options)} \u4e4b\u95f4\u7684\u6570\u5b57")

    result = questionary.select(prompt, choices=options, style=_Q_STYLE, qmark="").ask()
    if result is None:
        return None
    return options.index(result)


def prompt_input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def prompt_file(prompt: str, filetypes: list[tuple[str, str]] | None = None) -> str:
    import tkinter
    import tkinter.filedialog as fd
    hint = " (\u76f4\u63a5\u8f93\u5165\u8def\u5f84\u6216\u6309 Enter \u6d4f\u89c8\u6587\u4ef6)"
    val = input(f"{prompt}{hint}: ").strip().strip('"')
    if val:
        return val
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    result = fd.askopenfilename(
        title=prompt,
        filetypes=filetypes or [("All Files", "*.*")],
    )
    root.destroy()
    return result


def prompt_yes_no(prompt: str, default: bool = True) -> bool | None:
    if not sys.stdin.isatty():
        hint = "(Y/n)" if default else "(y/N)"
        try:
            val = input(f"{prompt} {hint}: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        if not val:
            return default
        return val in ("y", "yes", "\u662f")

    return questionary.confirm(prompt, default=default, style=_Q_STYLE, qmark="").ask()


def prompt_source_lang() -> str | None:
    if not sys.stdin.isatty():
        print("  1. English")
        print("  2. \u65e5\u672c\u8a9e")
        while True:
            try:
                val = input("\u6e90\u8bed\u8a00: ").strip()
                if not val:
                    return None
                idx = int(val)
                if idx == 1:
                    return "en"
                elif idx == 2:
                    return "ja"
            except (ValueError, EOFError):
                pass
            print("  \u8bf7\u8f93\u5165 1 \u6216 2")

    choice = questionary.select("\u6e90\u8bed\u8a00", choices=["English", "\u65e5\u672c\u8a9e"], style=_Q_STYLE, qmark="").ask()
    if choice is None:
        return None
    return {"English": "en", "\u65e5\u672c\u8a9e": "ja"}[choice]


def check_api_key() -> bool:
    if not config.API_KEY:
        print("  [\u9519\u8bef] \u672a\u8bbe\u7f6e TRANSLATE_API_KEY \u73af\u5883\u53d8\u91cf")
        print("  \u8bf7\u5148\u8fd0\u884c: set TRANSLATE_API_KEY=your_key")
        return False
    return True


def do_translate(subtitles: list[Subtitle], src: str, dst: str, keep_original: bool, output_path: str, original_path: str | None = None):
    texts = [s.text for s in subtitles]
    print(f"\n  \u5171 {len(texts)} \u6761\u5b57\u5e55\uff0c\u5f00\u59cb\u7ffb\u8bd1...\n")

    results = []
    batch_size = config.TRANSLATE_BATCH_SIZE
    total_batches = (len(texts) + batch_size - 1) // batch_size
    for i in FancyProgressBar(range(0, len(texts), batch_size), desc="  \u7ffb\u8bd1\u8fdb\u5ea6", total=total_batches):
        batch = texts[i : i + batch_size]
        translated = translate_batch(batch, source_lang=src, target_lang=dst)
        results.extend(translated)

    generate_srt(subtitles, results, output_path)

    if keep_original and original_path:
        generate_original_srt(subtitles, original_path)
        print(f"\n  \u5b8c\u6210! \u8f93\u51fa\u6587\u4ef6: {output_path}  +  {original_path}")
    else:
        print(f"\n  \u5b8c\u6210! \u8f93\u51fa\u6587\u4ef6: {output_path}")


def mode_file():
    if not check_api_key():
        return

    path = prompt_file("\u9009\u62e9\u5b57\u5e55\u6587\u4ef6", [("\u5b57\u5e55\u6587\u4ef6", "*.srt *.ass"), ("SRT", "*.srt"), ("ASS", "*.ass"), ("All Files", "*.*")])
    if not path:
        print("  [\u53d6\u6d88] \u672a\u9009\u62e9\u6587\u4ef6")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [\u9519\u8bef] \u6587\u4ef6\u4e0d\u5b58\u5728: {path}")
        return

    src = prompt_source_lang()
    if src is None:
        return
    print("  \u76ee\u6807\u8bed\u8a00\uff1a\u4e2d\u6587")
    dst = "zh"
    keep_original = prompt_yes_no("\u8f93\u51fa\u539f\u8f68\u5b57\u5e55?", True)
    if keep_original is None:
        return

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("\u8f93\u51fa\u6587\u4ef6\u8def\u5f84", default_out)

    if keep_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
    else:
        original_path = None

    print(f"\n  \u89e3\u6790\u5b57\u5e55\u6587\u4ef6: {path}")
    subtitles = parse_subtitle_file(path)
    print(f"  \u627e\u5230 {len(subtitles)} \u6761\u5b57\u5e55")

    do_translate(subtitles, src, dst, keep_original, output, original_path)


def mode_soft():
    if not check_api_key():
        return

    path = prompt_file("\u9009\u62e9\u89c6\u9891\u6587\u4ef6", [("\u89c6\u9891\u6587\u4ef6", "*.mp4 *.mkv *.avi *.mov *.ts"), ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("All Files", "*.*")])
    if not path:
        print("  [\u53d6\u6d88] \u672a\u9009\u62e9\u6587\u4ef6")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [\u9519\u8bef] \u6587\u4ef6\u4e0d\u5b58\u5728: {path}")
        return

    from core.soft_subtitle import get_subtitle_tracks
    from core.soft_subtitle import extract_soft_subtitle

    tracks = get_subtitle_tracks(path)
    if not tracks:
        print("  [\u9519\u8bef] \u672a\u627e\u5230\u5b57\u5e55\u8f68\u9053")
        return

    track_idx = prompt_choice("\u9009\u62e9\u5b57\u5e55\u8f68\u9053", [f"\u7d22\u5f15:{t['index']} {t['codec']} {t['language']}" for t in tracks])
    if track_idx is None:
        return
    selected_track = tracks[track_idx]["index"]

    src = prompt_source_lang()
    if src is None:
        return
    print("  \u76ee\u6807\u8bed\u8a00\uff1a\u4e2d\u6587")
    dst = "zh"
    keep_original = prompt_yes_no("\u8f93\u51fa\u539f\u8f68\u5b57\u5e55?", True)
    if keep_original is None:
        return

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("\u8f93\u51fa\u6587\u4ef6\u8def\u5f84", default_out)

    if keep_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
    else:
        original_path = None

    print(f"\n  \u63d0\u53d6\u5b57\u5e55\u8f68\u9053...")
    subtitles = extract_soft_subtitle(path, track_index=selected_track)
    print(f"  \u63d0\u53d6\u5230 {len(subtitles)} \u6761\u5b57\u5e55")

    do_translate(subtitles, src, dst, keep_original, output, original_path)


def mode_hard():
    if not check_api_key():
        return

    path = prompt_file("\u9009\u62e9\u89c6\u9891\u6587\u4ef6", [("\u89c6\u9891\u6587\u4ef6", "*.mp4 *.mkv *.avi *.mov *.ts"), ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("All Files", "*.*")])
    if not path:
        print("  [\u53d6\u6d88] \u672a\u9009\u62e9\u6587\u4ef6")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [\u9519\u8bef] \u6587\u4ef6\u4e0d\u5b58\u5728: {path}")
        return

    src = prompt_source_lang()
    if src is None:
        return
    print("  \u76ee\u6807\u8bed\u8a00\uff1a\u4e2d\u6587")
    dst = "zh"

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("\u8f93\u51fa\u6587\u4ef6\u8def\u5f84", default_out)

    from core.hard_subtitle import extract_hard_subtitle

    print(f"\n  \u91c7\u6837\u89c6\u9891\u5e27\u5e76 OCR \u8bc6\u522b (\u53ef\u80fd\u9700\u8981\u51e0\u5206\u949f)...")
    subtitles = extract_hard_subtitle(path)
    print(f"  OCR \u8bc6\u522b\u5230 {len(subtitles)} \u6761\u5b57\u5e55")

    do_translate(subtitles, src, dst, False, output, None)


def interactive_loop():
    modes = [
        ("\u7ffb\u8bd1\u5b57\u5e55\u6587\u4ef6 (.srt/.ass)", mode_file),
        ("\u7ffb\u8bd1\u89c6\u9891\u8f6f\u5b57\u5e55", mode_soft),
        ("\u7ffb\u8bd1\u89c6\u9891\u786c\u5b57\u5e55 (OCR)", mode_hard),
    ]
    ui = TerminalUI(modes)
    if sys.stdin.isatty():
        ui.run()
    else:
        ui.run_text()


def main():
    if len(sys.argv) > 1:
        from core_cli import cli
        cli()
    else:
        interactive_loop()


if __name__ == "__main__":
    main()