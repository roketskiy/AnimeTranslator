"""Welcome screen - mode selection dashboard."""

from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Horizontal, Vertical
from textual.message import Message
from rich.panel import Panel
from rich.text import Text

from ui.widgets.banner import Banner


class WelcomeScreen(Screen):
    """Welcome screen with mode selection cards."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "show_help", "Help"),
    ]

    class ModeSelected(Message):
        """Message sent when a mode is selected."""
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    def compose(self):
        yield Banner()
        yield Static("[bold #a0a0a0]选择翻译模式[/bold #a0a0a0]", id="mode-prompt")
        
        with Horizontal(id="mode-cards"):
            # Card 1: Subtitle file
            with Vertical(classes="mode-card"):
                yield Static("📄", classes="card-icon")
                yield Static("字幕文件", classes="card-title")
                yield Static("翻译 .srt / .ass 文件", classes="card-desc")
                yield Static("[dim]按 1 或 Enter 选择[/dim]", classes="card-hint")
            
            # Card 2: Soft subtitle
            with Vertical(classes="mode-card"):
                yield Static("🎬", classes="card-icon")
                yield Static("软字幕", classes="card-title")
                yield Static("提取并翻译视频内嵌字幕", classes="card-desc")
                yield Static("[dim]按 2 选择[/dim]", classes="card-hint")
            
            # Card 3: Hard subtitle
            with Vertical(classes="mode-card"):
                yield Static("🔍", classes="card-icon")
                yield Static("硬字幕 (OCR)", classes="card-title")
                yield Static("OCR 识别并翻译画面字幕", classes="card-desc")
                yield Static("[dim]按 3 选择[/dim]", classes="card-hint")

    def on_key(self, event) -> None:
        """Handle number keys for mode selection."""
        key = event.key
        if key == "1":
            self.post_message(self.ModeSelected("file"))
        elif key == "2":
            self.post_message(self.ModeSelected("soft"))
        elif key == "3":
            self.post_message(self.ModeSelected("hard"))

    def action_quit(self) -> None:
        """Quit application."""
        self.app.exit()

    def action_show_help(self) -> None:
        """Show help screen."""
        from ui.screens.help import HelpScreen
        self.app.push_screen(HelpScreen(context="welcome", step_name="模式选择"))
