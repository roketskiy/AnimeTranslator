"""Progress view widget for translation progress."""

from textual.widgets import Static, ProgressBar
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel


class ProgressView(Static):
    """Display translation progress with bar and statistics."""

    current: reactive[int] = reactive(0)
    total: reactive[int] = reactive(100)
    stage: reactive[str] = reactive("")  # e.g., "提取字幕", "翻译中"

    def __init__(self) -> None:
        super().__init__()

    def compose(self):
        yield Static("准备中...", id="stage-label")
        yield ProgressBar(total=100, id="progress-bar")
        yield Static("0 / 0", id="stats-label")

    def watch_current(self, current: int) -> None:
        self._update_display()

    def watch_total(self, total: int) -> None:
        self._update_display()

    def watch_stage(self, stage: str) -> None:
        self._update_display()

    def _update_display(self) -> None:
        stage_label = self.query_one("#stage-label", Static)
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        stats_label = self.query_one("#stats-label", Static)

        if self.stage:
            stage_label.update(f"[bold #d44020]{self.stage}[/bold #d44020]")
        
        if self.total > 0:
            percentage = int(self.current / self.total * 100)
            progress_bar.update(total=self.total, progress=self.current)
            stats_label.update(f"[bold]{self.current}[/bold] / [bold]{self.total}[/bold]  ({percentage}%)")
        else:
            progress_bar.update(total=100, progress=0)
            stats_label.update("准备中...")

    def set_progress(self, current: int, total: int) -> None:
        """Update progress."""
        self.current = current
        self.total = total

    def set_stage(self, stage: str) -> None:
        """Update stage label."""
        self.stage = stage
