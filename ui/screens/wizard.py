"""Wizard screen - main framework for translation workflow."""

from __future__ import annotations

from typing import Optional

from textual.screen import Screen
from textual.widgets import Static, Input, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.worker import Worker, WorkerState
from textual.message import Message
from rich.text import Text
from pathlib import Path

from ui.widgets.banner import Banner
from ui.widgets.step_indicator import StepIndicator
from ui.widgets.preview_panel import PreviewPanel
from ui.widgets.file_browser import FileBrowser
from ui.widgets.option_list import OptionList
from ui.widgets.input_panel import InputPanel
from ui.widgets.progress_view import ProgressView

from core import workflow


class WizardScreen(Screen):
    """Wizard framework with banner, step indicator, content area, and preview panel."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("h", "show_help", "Help"),
        ("p", "toggle_preview", "Toggle Preview"),
    ]

    mode: reactive[str] = reactive("")
    step: reactive[int] = reactive(1)
    total_steps: reactive[int] = reactive(4)
    
    # Collected parameters
    file_path: reactive[str] = reactive("")
    source_lang: reactive[str] = reactive("ja")
    keep_original: reactive[bool] = reactive(True)
    output_path: reactive[str] = reactive("")
    selected_track: reactive[int | None] = reactive(None)
    is_bilingual: reactive[bool] = reactive(False)
    preview_visible: reactive[bool] = reactive(True)

    # Step names per mode
    STEP_NAMES = {
        "file": ["选择字幕文件", "选择源语言", "输出选项", "执行翻译"],
        "soft": ["选择视频文件", "选择字幕轨道", "选择源语言", "输出选项", "执行翻译"],
        "hard": ["选择视频文件", "选择源语言", "输出选项", "执行翻译"],
    }

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.step = 1
        self.total_steps = len(self.STEP_NAMES.get(mode, []))
        self._tracks = []
        self._cancelled = False

    def compose(self):
        yield Banner()
        self.step_indicator = StepIndicator(
            step=self.step,
            total_steps=self.total_steps,
            step_name=self._get_step_name(),
        )
        yield self.step_indicator
        
        with Horizontal(id="wizard-main"):
            with Vertical(id="content-area"):
                yield Static("Loading...", id="content-placeholder")
            
            self.preview_panel = PreviewPanel()
            self.preview_panel.data = self._build_preview_data()
            yield self.preview_panel

    def _get_step_name(self) -> str:
        names = self.STEP_NAMES.get(self.mode, [])
        if 1 <= self.step <= len(names):
            return names[self.step - 1]
        return ""

    def _build_preview_data(self) -> dict:
        """Build preview data from current state."""
        data = {}
        
        if self.file_path:
            p = Path(self.file_path)
            data["file_name"] = p.name
            if p.exists():
                data["file_size"] = p.stat().st_size
            
            # Get file-specific info
            if self.mode == "file" and p.suffix.lower() in (".srt", ".ass"):
                try:
                    info = workflow.get_subtitle_info(self.file_path)
                    data["subtitle_count"] = info.get("count", 0)
                    data["subtitle_format"] = info.get("format", "")
                except Exception:
                    pass
            elif self.mode in ("soft", "hard"):
                try:
                    info = workflow.get_video_info(self.file_path)
                    data["duration"] = info.get("duration")
                except Exception:
                    pass
        
        if self.selected_track is not None and self._tracks:
            for track in self._tracks:
                if track.get("index") == self.selected_track:
                    data["track_info"] = track
                    break
        
        if self.source_lang:
            data["source_lang"] = self.source_lang
        
        if self.output_path:
            data["output_path"] = self.output_path
        
        if self.mode != "hard":
            data["keep_original"] = self.keep_original
        else:
            data["bilingual"] = self.is_bilingual
        
        return data

    def _update_preview(self) -> None:
        """Update preview panel with current data."""
        self.preview_panel.data = self._build_preview_data()

    def watch_step(self, step: int) -> None:
        """React to step changes."""
        self.step_indicator.step = step
        self.step_indicator.step_name = self._get_step_name()
        self._mount_step_content()

    def watch_preview_visible(self, visible: bool) -> None:
        """Toggle preview panel visibility."""
        preview = self.query_one(PreviewPanel)
        preview.display = visible

    def on_mount(self) -> None:
        """Mount initial step content."""
        self._mount_step_content()

    def _mount_step_content(self) -> None:
        """Mount the appropriate widget for current step."""
        content_area = self.query_one("#content-area", Vertical)
        
        # Remove existing content
        for child in list(content_area.children):
            child.remove()
        
        if self.mode == "file":
            self._mount_file_step(content_area)
        elif self.mode == "soft":
            self._mount_soft_step(content_area)
        elif self.mode == "hard":
            self._mount_hard_step(content_area)

    def _mount_file_step(self, container: Vertical) -> None:
        """Mount content for file mode."""
        if self.step == 1:
            # Select subtitle file
            browser = FileBrowser(extensions=[".srt", ".ass"])
            browser.focus()
            container.mount(browser)
        elif self.step == 2:
            # Select source language
            options = [("日本語", "ja"), ("English", "en")]
            option_list = OptionList(options)
            option_list.focus()
            container.mount(Static("[bold]请选择源语言[/bold]"))
            container.mount(option_list)
        elif self.step == 3:
            # Output options
            keep_options = [("是", "true"), ("否", "false")]
            keep_list = OptionList(keep_options)
            keep_list.focus()
            
            p = Path(self.file_path) if self.file_path else Path(".")
            default_out = str(p.with_suffix(".zh.srt"))
            output_input = InputPanel(
                label="输出文件路径",
                default=default_out,
                show_browse=True,
                filetypes=[("SRT", "*.srt"), ("All Files", "*.*")],
            )
            
            container.mount(Static("[bold]是否保留原轨字幕?[/bold]"))
            container.mount(keep_list)
            container.mount(output_input)
        elif self.step == 4:
            # Execute
            progress = ProgressView()
            container.mount(Static("[bold #d44020]开始翻译...[/bold #d44020]"))
            container.mount(progress)
            self._start_translation(progress)

    def _mount_soft_step(self, container: Vertical) -> None:
        """Mount content for soft subtitle mode."""
        if self.step == 1:
            # Select video file
            browser = FileBrowser(extensions=[".mp4", ".mkv", ".avi", ".mov", ".ts"])
            browser.focus()
            container.mount(browser)
        elif self.step == 2:
            # Select subtitle track
            if not self._tracks:
                try:
                    self._tracks = workflow.get_soft_subtitle_tracks(self.file_path)
                except Exception as e:
                    container.mount(Static(f"[red]获取字幕轨道失败: {e}[/red]"))
                    return
            
            if not self._tracks:
                container.mount(Static("[red]未找到字幕轨道[/red]"))
                return
            
            options = []
            for track in self._tracks:
                label = f"索引:{track['index']} {track['codec']} {track['language']}"
                if track.get('title'):
                    label += f" ({track['title']})"
                options.append((label, str(track['index'])))
            
            option_list = OptionList(options)
            option_list.focus()
            container.mount(Static("[bold]请选择字幕轨道[/bold]"))
            container.mount(option_list)
        elif self.step == 3:
            # Select source language
            options = [("日本語", "ja"), ("English", "en")]
            option_list = OptionList(options)
            option_list.focus()
            container.mount(Static("[bold]请选择源语言[/bold]"))
            container.mount(option_list)
        elif self.step == 4:
            # Output options
            keep_options = [("是", "true"), ("否", "false")]
            keep_list = OptionList(keep_options)
            keep_list.focus()
            
            p = Path(self.file_path) if self.file_path else Path(".")
            default_out = str(p.with_suffix(".zh.srt"))
            output_input = InputPanel(
                label="输出文件路径",
                default=default_out,
                show_browse=True,
                filetypes=[("SRT", "*.srt"), ("All Files", "*.*")],
            )
            
            container.mount(Static("[bold]是否保留原轨字幕?[/bold]"))
            container.mount(keep_list)
            container.mount(output_input)
        elif self.step == 5:
            # Execute
            progress = ProgressView()
            container.mount(Static("[bold #d44020]开始提取并翻译...[/bold #d44020]"))
            container.mount(progress)
            self._start_translation(progress)

    def _mount_hard_step(self, container: Vertical) -> None:
        """Mount content for hard subtitle (OCR) mode."""
        if self.step == 1:
            # Select video file
            browser = FileBrowser(extensions=[".mp4", ".mkv", ".avi", ".mov", ".ts"])
            browser.focus()
            container.mount(browser)
        elif self.step == 2:
            # Select source language
            options = [("日本語", "ja"), ("English", "en")]
            option_list = OptionList(options)
            option_list.focus()
            container.mount(Static("[bold]请选择源语言[/bold]"))
            container.mount(option_list)
        elif self.step == 3:
            # Output options
            bilingual_options = [("是", "true"), ("否", "false")]
            bilingual_list = OptionList(bilingual_options)
            bilingual_list.focus()
            
            p = Path(self.file_path) if self.file_path else Path(".")
            default_out = str(p.with_suffix(".zh.srt"))
            output_input = InputPanel(
                label="输出文件路径",
                default=default_out,
                show_browse=True,
                filetypes=[("SRT", "*.srt"), ("All Files", "*.*")],
            )
            
            container.mount(Static("[bold]是否输出双语字幕?[/bold]"))
            container.mount(bilingual_list)
            container.mount(output_input)
        elif self.step == 4:
            # Execute
            progress = ProgressView()
            container.mount(Static("[bold #d44020]开始 OCR 识别并翻译...[/bold #d44020]"))
            container.mount(progress)
            self._start_translation(progress)

    # Event handlers for widgets
    def on_file_browser_selected(self, event: FileBrowser.Selected) -> None:
        """Handle file selection."""
        self.file_path = event.path
        self._update_preview()
        self._next_step()

    def on_option_list_selected(self, event: OptionList.Selected) -> None:
        """Handle option selection."""
        value = event.value
        
        if self.mode == "file":
            if self.step == 2:
                self.source_lang = value
                self._update_preview()
                self._next_step()
            elif self.step == 3:
                self.keep_original = value == "true"
                # Don't advance yet, wait for input panel
        elif self.mode == "soft":
            if self.step == 2:
                self.selected_track = int(value)
                self._update_preview()
                self._next_step()
            elif self.step == 3:
                self.source_lang = value
                self._update_preview()
                self._next_step()
            elif self.step == 4:
                self.keep_original = value == "true"
        elif self.mode == "hard":
            if self.step == 2:
                self.source_lang = value
                self._update_preview()
                self._next_step()
            elif self.step == 3:
                self.is_bilingual = value == "true"

    def on_input_panel_submitted(self, event: InputPanel.Submitted) -> None:
        """Handle input submission."""
        if self.step == 3:
            self.output_path = event.value
            self._update_preview()
            self._next_step()

    def _next_step(self) -> None:
        """Advance to next step."""
        if self.step < self.total_steps:
            self.step += 1

    def action_go_back(self) -> None:
        """Go back to previous step or welcome screen."""
        if self.step > 1:
            self.step -= 1
        else:
            self.app.pop_screen()

    def action_show_help(self) -> None:
        """Show help screen."""
        from ui.screens.help import HelpScreen
        self.app.push_screen(HelpScreen(
            context=self.mode,
            step_name=self._get_step_name(),
        ))

    def action_toggle_preview(self) -> None:
        """Toggle preview panel visibility."""
        self.preview_visible = not self.preview_visible

    def _start_translation(self, progress_view: ProgressView) -> None:
        """Start translation in background worker."""
        self._cancelled = False
        
        def progress_callback(current: int, total: int) -> None:
            if not self._cancelled:
                self.app.call_from_thread(
                    lambda: progress_view.set_progress(current, total)
                )
        
        def do_work() -> dict:
            try:
                if self.mode == "file":
                    return workflow.translate_subtitle_file(
                        self.file_path,
                        src=self.source_lang,
                        keep_original=self.keep_original,
                        output_path=self.output_path or None,
                        progress_callback=progress_callback,
                    )
                elif self.mode == "soft":
                    return workflow.translate_soft_subtitle(
                        self.file_path,
                        track_index=self.selected_track,
                        src=self.source_lang,
                        keep_original=self.keep_original,
                        output_path=self.output_path or None,
                        progress_callback=progress_callback,
                    )
                elif self.mode == "hard":
                    return workflow.translate_hard_subtitle(
                        self.file_path,
                        src=self.source_lang,
                        output_path=self.output_path or None,
                        bilingual=self.is_bilingual,
                        progress_callback=progress_callback,
                    )
            except Exception as e:
                return {"error": str(e)}
        
        self.run_worker(do_work, thread=True)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            container = self.query_one("#content-area", Vertical)
            
            if isinstance(result, dict) and "error" in result:
                container.mount(Static(f"[red]翻译失败: {result['error']}[/red]"))
            else:
                container.mount(Static(f"[green]翻译完成![/green]"))
                container.mount(Static(f"输出: {result.get('output_path', '')}"))
                if result.get('original_path'):
                    container.mount(Static(f"原轨: {result['original_path']}"))
                
                # Update preview with final result
                self._update_preview()
        elif event.state == WorkerState.ERROR:
            container = self.query_one("#content-area", Vertical)
            container.mount(Static(f"[red]翻译出错[/red]"))



