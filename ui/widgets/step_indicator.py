"""Step indicator widget."""

from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text


class StepIndicator(Static):
    """Display current step: Step X/Y ── Step Name"""

    step: reactive[int] = reactive(1)
    total_steps: reactive[int] = reactive(4)
    step_name: reactive[str] = reactive("")

    def __init__(self, step: int = 1, total_steps: int = 4, step_name: str = "") -> None:
        super().__init__()
        self.step = step
        self.total_steps = total_steps
        self.step_name = step_name

    def watch_step(self, step: int) -> None:
        self.update(self._render_text())

    def watch_total_steps(self, total_steps: int) -> None:
        self.update(self._render_text())

    def watch_step_name(self, step_name: str) -> None:
        self.update(self._render_text())

    def _render_text(self) -> Text:
        text = Text()
        text.append(f"Step {self.step}/{self.total_steps}", style="bold #ffd700")
        text.append("  ──  ", style="#333333")
        text.append(self.step_name, style="bold white")
        return text

    def render(self) -> Text:
        return self._render_text()
