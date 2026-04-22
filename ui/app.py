"""Textual App main entry point."""

from textual.app import App

from ui.screens.welcome import WelcomeScreen
from ui.screens.wizard import WizardScreen


class AnimeTranslatorApp(App):
    """AnimeTranslator TUI application."""

    CSS_PATH = "styles.tcss"
    
    TITLE = "AnimeTranslator"
    SUB_TITLE = "视频字幕翻译工具"

    def on_mount(self) -> None:
        """Push welcome screen on mount."""
        self.push_screen(WelcomeScreen())

    def on_welcome_screen_mode_selected(self, event: WelcomeScreen.ModeSelected) -> None:
        """Handle mode selection from welcome screen."""
        self.push_screen(WizardScreen(mode=event.mode))


if __name__ == "__main__":
    app = AnimeTranslatorApp()
    app.run()
