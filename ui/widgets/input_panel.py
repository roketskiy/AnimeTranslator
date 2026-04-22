"""Input panel with optional file browser integration."""

from typing import Optional
from textual.widgets import Static, Input, Button
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.message import Message
import tkinter
import tkinter.filedialog as fd


class InputPanel(Static):
    """Text input with optional file browser button."""

    class Submitted(Message):
        """Message sent when value is submitted."""
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    value: reactive[str] = reactive("")

    def __init__(self, label: str = "", default: str = "", show_browse: bool = False, filetypes: Optional[list[tuple[str, str]]] = None) -> None:
        super().__init__()
        self.label = label
        self.default = default
        self.show_browse = show_browse
        self.filetypes = filetypes or [("All Files", "*.*")]

    def compose(self):
        yield Static(self.label, classes="input-label")
        with Horizontal():
            input_widget = Input(value=self.default, placeholder=self.default or "请输入...")
            input_widget.focus()
            yield input_widget
            if self.show_browse:
                yield Button("浏览...", id="browse-btn")

    def on_input_submitted(self, event) -> None:
        """Handle Enter on input."""
        self.value = event.value
        self.post_message(self.Submitted(event.value))

    def on_button_pressed(self, event) -> None:
        """Handle browse button."""
        if event.button.id == "browse-btn":
            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result = fd.askopenfilename(
                title=self.label,
                filetypes=self.filetypes,
            )
            root.destroy()
            if result:
                input_widget = self.query_one(Input)
                input_widget.value = result
                self.value = result
                self.post_message(self.Submitted(result))
