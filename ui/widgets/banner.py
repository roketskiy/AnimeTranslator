"""ASCII Banner widget with 3D shadow effect."""

from textual.widgets import Static
from rich.text import Text

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

_COLOR = "#d44020"


def _render_banner(text: str, spacing: int = 4) -> list[str]:
    base = [""] * 5
    for i, ch in enumerate(text.upper()):
        pat = _LETTERS.get(ch, ["     "] * 5)
        for r in range(5):
            sep = " " * spacing if i > 0 else ""
            base[r] += sep + pat[r]
    lines = []
    for row in base:
        expanded = "".join(c * 2 for c in row)
        lines.append(expanded)
        lines.append(expanded)
    return lines


def _render_shadow(text: str, spacing: int = 4) -> list[str]:
    base = [""] * 5
    for i, ch in enumerate(text.upper()):
        pat = _SHADOW_LETTERS.get(ch, ["     "] * 5)
        for r in range(5):
            sep = " " * spacing if i > 0 else ""
            base[r] += sep + pat[r]
    lines = []
    for row in base:
        expanded = "".join(c * 2 for c in row)
        lines.append(expanded)
    return lines


def _merge_banner_line(solid: str, shadow: str, shadow_offset: int = 1) -> Text:
    max_len = max(len(solid), len(shadow) + shadow_offset)
    result = Text()
    for i in range(max_len):
        si = i
        shi = i - shadow_offset
        has_solid = si < len(solid) and solid[si] != " "
        has_shadow = 0 <= shi < len(shadow) and shadow[shi] != " "
        if has_solid:
            result.append(solid[si], style=f"bold {_COLOR}")
        elif has_shadow:
            result.append(shadow[shi], style="dim #555555")
        else:
            result.append(" ")
    return result


def render_banner_text() -> Text:
    """Render the full banner as Rich Text."""
    solid_lines = _render_banner("ANIME", 4) + [""] + _render_banner("TRANS", 4)
    shadow_lines = _render_shadow("ANIME", 4) + [""] + _render_shadow("TRANS", 4)

    h_shift = 1
    v_shift = 1

    total = max(len(solid_lines), len(shadow_lines) + v_shift)
    result = Text()

    for i in range(total):
        solid = solid_lines[i] if i < len(solid_lines) else None
        shadow = shadow_lines[i - v_shift] if (i >= v_shift and i - v_shift < len(shadow_lines)) else None

        if solid and solid.strip():
            if shadow and shadow.strip():
                line = _merge_banner_line(solid, shadow, h_shift)
            else:
                line = Text(solid, style=f"bold {_COLOR}")
            result.append("  ")
            result.append(line)
        elif shadow and shadow.strip():
            result.append("  ")
            result.append(Text(" " * h_shift + shadow, style="dim #555555"))
        result.append("\n")

    return result


class Banner(Static):
    """ASCII pixel art banner widget."""

    def __init__(self) -> None:
        super().__init__()

    def render(self) -> Text:
        return render_banner_text()
