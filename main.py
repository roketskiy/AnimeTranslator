from __future__ import annotations

import logging
import sys
import tkinter
import tkinter.filedialog as fd
from pathlib import Path

import questionary
from questionary import Style
from tqdm import tqdm

import config
from core.subtitle_parser import parse_subtitle_file, Subtitle
from core.translator import translate_batch
from core.srt_generator import generate_srt, generate_bilingual_srt, generate_original_srt

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


_LETTERS = {
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
}

_SHADOW_LETTERS = {
    "A": [" ░░░ ", "░   ░", "░░░░░", "░   ░", "░   ░"],
    "N": ["░   ░", "░░  ░", "░ ░ ░", "░  ░░", "░   ░"],
    "I": ["░░░░░", "  ░  ", "  ░  ", "  ░  ", "░░░░░"],
    "M": ["░   ░", "░░ ░░", "░ ░ ░", "░   ░", "░   ░"],
    "E": ["░░░░░", "░    ", "░░░░ ", "░    ", "░░░░░"],
    "T": ["░░░░░", "  ░  ", "  ░  ", "  ░  ", "  ░  "],
    "R": ["░░░░ ", "░   ░", "░░░░ ", "░  ░ ", "░   ░"],
    "S": [" ░░░░", "░    ", " ░░░ ", "    ░", "░░░░ "],
    "L": ["░    ", "░    ", "░    ", "░    ", "░░░░░"],
    "O": [" ░░░ ", "░   ░", "░   ░", "░   ░", " ░░░ "],
}

_COLOR = "\033[38;2;212;64;32m"
_RESET = "\033[0m"


def _render_banner(text: str, spacing: int = 4) -> list[str]:
    lines = [""] * 5
    for i, ch in enumerate(text.upper()):
        pat = _LETTERS.get(ch, ["     "] * 5)
        for r in range(5):
            sep = " " * spacing if i > 0 else ""
            lines[r] += sep + pat[r]
    return lines


def _render_shadow(text: str, spacing: int = 4) -> list[str]:
    lines = [""] * 5
    for i, ch in enumerate(text.upper()):
        pat = _SHADOW_LETTERS.get(ch, ["     "] * 5)
        for r in range(5):
            sep = " " * spacing if i > 0 else ""
            lines[r] += sep + pat[r]
    return lines


def _merge_banner_line(solid: str, shadow: str, shadow_offset: int = 1) -> str:
    max_len = max(len(solid), len(shadow) + shadow_offset)
    result = []
    in_color = False
    for i in range(max_len):
        si = i
        shi = i - shadow_offset
        has_solid = si < len(solid) and solid[si] != " "
        has_shadow = 0 <= shi < len(shadow) and shadow[shi] != " "
        if has_solid:
            if not in_color:
                result.append(_COLOR)
                in_color = True
            result.append(solid[si])
        else:
            if in_color:
                result.append(_RESET)
                in_color = False
            if has_shadow:
                result.append(shadow[shi])
            else:
                result.append(" ")
    if in_color:
        result.append(_RESET)
    return "".join(result)


def print_banner():
    solid_lines = _render_banner("ANIME", 4) + [""] + _render_banner("TRANS", 4)
    shadow_lines = _render_shadow("ANIME", 4) + [""] + _render_shadow("TRANS", 4)

    print()
    for solid, shadow in zip(solid_lines, shadow_lines):
        merged = _merge_banner_line(solid, shadow, shadow_offset=1)
        print(f"  {merged}")
    print()
    print("        视频字幕翻译工具  v1.0")
    print()


_Q_STYLE = Style([
    ("selected", "fg:#d44020"),
])


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
            print(f"  请输入 1-{len(options)} 之间的数字")

    result = questionary.select(prompt, choices=options, style=_Q_STYLE).ask()
    if result is None:
        return None
    return options.index(result)


def prompt_input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def prompt_file(prompt: str, filetypes: list[tuple[str, str]] | None = None) -> str:
    hint = " (直接输入路径或按 Enter 浏览文件)"
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
        return val in ("y", "yes", "是")

    return questionary.confirm(prompt, default=default, style=_Q_STYLE).ask()


def prompt_source_lang() -> str | None:
    if not sys.stdin.isatty():
        print("  1. English")
        print("  2. 日本語")
        while True:
            try:
                val = input("源语言: ").strip()
                if not val:
                    return None
                idx = int(val)
                if idx == 1:
                    return "en"
                elif idx == 2:
                    return "ja"
            except (ValueError, EOFError):
                pass
            print("  请输入 1 或 2")

    choice = questionary.select("源语言", choices=["English", "日本語"], style=_Q_STYLE).ask()
    if choice is None:
        return None
    return {"English": "en", "日本語": "ja"}[choice]


def check_api_key() -> bool:
    if not config.API_KEY:
        print("  [错误] 未设置 TRANSLATE_API_KEY 环境变量")
        print("  请先运行: set TRANSLATE_API_KEY=your_key")
        return False
    return True


def do_translate(subtitles: list[Subtitle], src: str, dst: str, keep_original: bool, output_path: str, original_path: str | None = None):
    texts = [s.text for s in subtitles]
    print(f"\n  共 {len(texts)} 条字幕，开始翻译...\n")

    results = []
    batch_size = config.TRANSLATE_BATCH_SIZE
    for i in tqdm(range(0, len(texts), batch_size), desc="  翻译进度"):
        batch = texts[i : i + batch_size]
        translated = translate_batch(batch, source_lang=src, target_lang=dst)
        results.extend(translated)

    generate_srt(subtitles, results, output_path)

    if keep_original and original_path:
        generate_original_srt(subtitles, original_path)
        print(f"\n  完成! 输出文件: {output_path}  +  {original_path}")
    else:
        print(f"\n  完成! 输出文件: {output_path}")


def mode_file():
    if not check_api_key():
        return

    path = prompt_file("选择字幕文件", [("字幕文件", "*.srt *.ass"), ("SRT", "*.srt"), ("ASS", "*.ass"), ("All Files", "*.*")])
    if not path:
        print("  [取消] 未选择文件")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [错误] 文件不存在: {path}")
        return

    src = prompt_source_lang()
    if src is None:
        return
    print("  目标语言：中文")
    dst = "zh"
    keep_original = prompt_yes_no("输出原轨字幕?", True)
    if keep_original is None:
        return

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("输出文件路径", default_out)

    if keep_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
    else:
        original_path = None

    print(f"\n  解析字幕文件: {path}")
    subtitles = parse_subtitle_file(path)
    print(f"  找到 {len(subtitles)} 条字幕")

    do_translate(subtitles, src, dst, keep_original, output, original_path)


def mode_soft():
    if not check_api_key():
        return

    path = prompt_file("选择视频文件", [("视频文件", "*.mp4 *.mkv *.avi *.mov *.ts"), ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("All Files", "*.*")])
    if not path:
        print("  [取消] 未选择文件")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [错误] 文件不存在: {path}")
        return

    from core.soft_subtitle import get_subtitle_tracks
    from core.soft_subtitle import extract_soft_subtitle

    tracks = get_subtitle_tracks(path)
    if not tracks:
        print("  [错误] 未找到字幕轨道")
        return

    track_idx = prompt_choice("选择字幕轨道", [f"索引:{t['index']} {t['codec']} {t['language']}" for t in tracks])
    if track_idx is None:
        return
    selected_track = tracks[track_idx]["index"]

    src = prompt_source_lang()
    if src is None:
        return
    print("  目标语言：中文")
    dst = "zh"
    keep_original = prompt_yes_no("输出原轨字幕?", True)
    if keep_original is None:
        return

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("输出文件路径", default_out)

    if keep_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
    else:
        original_path = None

    print(f"\n  提取字幕轨道...")
    subtitles = extract_soft_subtitle(path, track_index=selected_track)
    print(f"  提取到 {len(subtitles)} 条字幕")

    do_translate(subtitles, src, dst, keep_original, output, original_path)


def mode_hard():
    if not check_api_key():
        return

    path = prompt_file("选择视频文件", [("视频文件", "*.mp4 *.mkv *.avi *.mov *.ts"), ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("All Files", "*.*")])
    if not path:
        print("  [取消] 未选择文件")
        return

    p = Path(path)
    if not p.exists():
        print(f"  [错误] 文件不存在: {path}")
        return

    src = prompt_source_lang()
    if src is None:
        return
    print("  目标语言：中文")
    dst = "zh"

    default_out = str(p.with_suffix(f".{dst}.srt"))
    output = prompt_input("输出文件路径", default_out)

    from core.hard_subtitle import extract_hard_subtitle

    print(f"\n  采样视频帧并 OCR 识别 (可能需要几分钟)...")
    subtitles = extract_hard_subtitle(path)
    print(f"  OCR 识别到 {len(subtitles)} 条字幕")

    do_translate(subtitles, src, dst, False, output, None)


def interactive_loop():
    modes = [
        ("翻译字幕文件 (.srt/.ass)", mode_file),
        ("翻译视频软字幕", mode_soft),
        ("翻译视频硬字幕 (OCR)", mode_hard),
    ]

    def _loop_text():
        while True:
            print()
            print("── 请选择模式 ──")
            for i, (label, _) in enumerate(modes, 1):
                print(f"  {i}. {label}")
            print(f"  0. 退出")
            try:
                choice = input("\n请输入编号: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  再见!")
                break

            if choice == "0":
                print("  再见!")
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(modes):
                    print()
                    try:
                        modes[idx][1]()
                    except Exception as e:
                        print(f"\n  [错误] {e}")
                        log.exception("Error in mode %s", modes[idx][0])
                else:
                    print("  无效选择")
            except ValueError:
                print("  请输入有效数字")

    def _loop_tui():
        while True:
            print()
            choice = questionary.select(
                "── 请选择模式 ──",
                choices=[label for label, _ in modes] + ["退出"],
                style=_Q_STYLE,
            ).ask()

            if choice is None or choice == "退出":
                print("  再见!")
                break

            for label, func in modes:
                if choice == label:
                    print()
                    try:
                        func()
                    except Exception as e:
                        print(f"\n  [错误] {e}")
                        log.exception("Error in mode %s", label)
                    break

    if sys.stdin.isatty():
        _loop_tui()
    else:
        _loop_text()


def main():
    print_banner()
    if len(sys.argv) > 1:
        from core_cli import cli
        cli()
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
