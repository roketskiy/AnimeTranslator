"""Option list widget for single-choice selection."""

from textual.widgets import OptionList as TextualOptionList
from textual.reactive import reactive
from textual.message import Message


class OptionList(TextualOptionList):
    """Single-choice option list with keyboard navigation."""

    class Selected(Message):
        """Message sent when an option is selected."""
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, options: list[tuple[str, str]], *args, **kwargs) -> None:
        """Initialize with list of (display, value) tuples."""
        super().__init__(*args, **kwargs)
        self._options_map = {}
        for display, value in options:
            self._options_map[display] = value
            self.add_option(display)

    def on_option_list_option_selected(self, event) -> None:
        """Handle selection."""
        display = event.option.prompt
        value = self._options_map.get(str(display), str(display))
        self.post_message(self.Selected(value))
