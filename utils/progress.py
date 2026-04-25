"""虚实结合进度条组件。"""
from __future__ import annotations

from tqdm import tqdm

# 主题色与样式代码（与项目现有配色保持一致）
_C_THEME = "\033[38;2;212;64;32m"  # 主题红 #d44020
_C_BOLD = "\033[1m"
_C_DIM = "\033[2m"
_C_RESET = "\033[0m"


class FancyProgressBar(tqdm):
    """虚实结合进度条。

    - 已完成部分：实心块 █（主题色）
    - 未完成部分：虚线块 ░（灰色）
    - 左右边界：▶ ◀（主题色箭头）
    - 右侧显示：批次进度、剩余时间、百分比
    """

    BAR_WIDTH = 28

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("bar_format", "{l_bar}{bar}{r_bar}")
        super().__init__(*args, **kwargs)

    @staticmethod
    def format_meter(
        n,
        total,
        elapsed,
        ncols=None,
        prefix="",
        ascii=False,
        unit="it",
        unit_scale=False,
        rate=None,
        bar_format=None,
        postfix=None,
        unit_divisor=1000,
        initial=0,
        colour=None,
        **extra_kwargs,
    ):
        # ---- 计算进度条长度 ----
        if total:
            frac = n / total
            filled_len = int(FancyProgressBar.BAR_WIDTH * frac)
        else:
            frac = 0
            filled_len = 0

        empty_len = FancyProgressBar.BAR_WIDTH - filled_len

        C = _C_THEME
        B = _C_BOLD
        D = _C_DIM
        R = _C_RESET

        # 虚实结合的 bar：实心 █ + 虚线 ░
        bar = f"{C}{'█' * filled_len}{R}{D}{'░' * empty_len}{R}"

        # ---- 统计信息（复用 tqdm 工具函数） ----
        if rate is None and elapsed > 0:
            rate = (n - initial) / elapsed

        if total and rate and rate > 0:
            remaining = (total - n) / rate
            remaining_str = tqdm.format_interval(remaining)
        else:
            remaining_str = "?"

        n_fmt = str(n)
        total_fmt = str(total) if total else "?"

        if total:
            pct = frac * 100
            pct_str = f"{pct:5.1f}%"
        else:
            pct_str = "  ?  %"

        desc = f"{prefix}: " if prefix else ""

        # ---- 组装输出 ----
        left = f"  {desc}"
        mid = f"{C}▶{R} {bar} {C}◀{R}"
        right = f"  {B}{n_fmt}{R}/{total_fmt} 批次  ⏳ {remaining_str}  {C}{pct_str}{R}"

        return f"{left}{mid}{right}"
