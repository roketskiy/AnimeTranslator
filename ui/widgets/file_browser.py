"""File browser widget using DirectoryTree."""

from typing import Optional
from textual.widgets import DirectoryTree, Static
from textual.reactive import reactive
from textual.message import Message
from pathlib import Path


class FileBrowser(Static):
    """File browser with extension filtering."""

    class Selected(Message):
        """Message sent when a file is selected."""
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    path: reactive[str] = reactive("")

    def __init__(self, extensions: Optional[list[str]] = None) -> None:
        super().__init__()
        self.extensions = [ext.lower() for ext in (extensions or [])]
        self._tree = None

    def compose(self):
        yield Static("[dim]↑/↓ 导航, Enter 选择, . 显示/隐藏隐藏文件[/dim]", classes="hint")
        tree = DirectoryTree(Path.home())
        self._tree = tree
        yield tree

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter paths by extension."""
        if not self.extensions:
            return paths
        
        filtered = []
        for path in paths:
            if path.is_dir():
                filtered.append(path)
            elif path.suffix.lower() in self.extensions:
                filtered.append(path)
        return filtered

    def on_directory_tree_file_selected(self, event) -> None:
        """Handle file selection."""
        path = str(event.path)
        self.path = path
        self.post_message(self.Selected(path))

    def on_directory_tree_directory_selected(self, event) -> None:
        """Handle directory selection - navigate into it."""
        pass  # DirectoryTree handles navigation automatically
