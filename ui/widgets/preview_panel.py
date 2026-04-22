"""Preview panel widget showing collected parameters and file metadata."""

from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel


class PreviewPanel(Static):
    """Display file metadata and collected parameters."""

    data: reactive[dict] = reactive({}, always_update=True)

    def __init__(self) -> None:
        super().__init__()
        self.data = {}

    def watch_data(self, data: dict) -> None:
        self.update(self._render_content())

    def _render_content(self) -> Panel:
        lines = []
        
        # File info section
        if "file_name" in self.data:
            lines.append(f"[bold #d44020]文件[/bold #d44020]")
            lines.append(f"  名称: {self.data.get('file_name', '')}")
            size = self.data.get('file_size', 0)
            if size:
                size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
                lines.append(f"  大小: {size_str}")
            if "duration" in self.data and self.data["duration"]:
                lines.append(f"  时长: {self.data['duration']}")
            if "subtitle_count" in self.data:
                lines.append(f"  字幕数: {self.data['subtitle_count']} 条")
            if "subtitle_format" in self.data:
                lines.append(f"  格式: {self.data['subtitle_format'].upper()}")
            lines.append("")

        # Track info (for soft subtitle)
        if "track_info" in self.data:
            track = self.data["track_info"]
            lines.append(f"[bold #d44020]字幕轨道[/bold #d44020]")
            lines.append(f"  索引: {track.get('index', '')}")
            lines.append(f"  编码: {track.get('codec', '')}")
            lines.append(f"  语言: {track.get('language', '')}")
            if track.get('title'):
                lines.append(f"  标题: {track['title']}")
            lines.append("")

        # Translation params
        if "source_lang" in self.data:
            lines.append(f"[bold #d44020]翻译参数[/bold #d44020]")
            src = self.data.get("source_lang", "")
            src_display = {"ja": "日本語", "en": "English"}.get(src, src)
            lines.append(f"  源语言: {src_display}")
            lines.append(f"  目标语言: 中文")
            if "keep_original" in self.data:
                lines.append(f"  保留原轨: {'是' if self.data['keep_original'] else '否'}")
            if "bilingual" in self.data:
                lines.append(f"  双语输出: {'是' if self.data['bilingual'] else '否'}")
            lines.append("")

        # Output path
        if "output_path" in self.data:
            lines.append(f"[bold #d44020]输出[/bold #d44020]")
            lines.append(f"  {self.data['output_path']}")
            if self.data.get("original_path"):
                lines.append(f"  {self.data['original_path']}")
            lines.append("")

        content = "\n".join(lines) if lines else "[dim]暂无信息[/dim]"
        
        return Panel(
            content,
            title="[bold #a0a0a0]预览[/bold #a0a0a0]",
            border_style="#333333",
            padding=(0, 1),
        )

    def render(self) -> Panel:
        return self._render_content()
