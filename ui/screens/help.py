"""Help screen - modal overlay showing keyboard shortcuts."""

from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Vertical, Horizontal
from rich.panel import Panel
from rich.text import Text


class HelpScreen(Screen):
    """Modal help panel showing context-aware shortcuts."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]

    def __init__(self, context: str = "", step_name: str = "") -> None:
        super().__init__()
        self.context = context
        self.step_name = step_name

    def compose(self):
        with Vertical(id="help-container"):
            yield Static("[bold]键盘快捷键[/bold]", id="help-title")
            yield Static(self._render_content(), id="help-content")
            yield Button("关闭 (Esc)", id="close-btn", variant="primary")

    def _render_content(self) -> str:
        lines = [
            "[bold #d44020]全局[/bold #d44020]",
            "  ↑/↓          导航选项",
            "  Enter        确认选择",
            "  Esc          返回上一步",
            "  Tab          切换焦点",
            "  h / ?        显示帮助",
            "  q            退出应用（仅在首页）",
            "  p            切换预览面板",
            "",
        ]

        if self.step_name:
            lines.append(f"[bold #d44020]当前步骤: {self.step_name}[/bold #d44020]")
            
            if "文件" in self.step_name or "视频" in self.step_name:
                lines.extend([
                    "  ↑/↓          导航文件",
                    "  Enter        进入目录或选择文件",
                    "  .            显示/隐藏隐藏文件",
                ])
            elif "轨道" in self.step_name or "语言" in self.step_name:
                lines.extend([
                    "  ↑/↓          选择选项",
                    "  Enter        确认",
                ])
            elif "输出" in self.step_name:
                lines.extend([
                    "  ↑/↓          切换选项",
                    "  Enter        确认",
                    "  Tab          切换到路径输入",
                ])
            elif "执行" in self.step_name or "翻译" in self.step_name:
                lines.extend([
                    "  Esc          取消翻译",
                ])
            
            lines.append("")

        return "\n".join(lines)

    def on_button_pressed(self, event) -> None:
        if event.button.id == "close-btn":
            self.app.pop_screen()
