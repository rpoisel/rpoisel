from dataclasses import dataclass

import rapidfuzz
import typer

from ..util.process import run_shell_check


@dataclass
class BrowserNames:
    name: str
    alt_name: str


KNOWN_BROWSERS: dict[str, BrowserNames] = {
    "chrome": BrowserNames("google-chrome", "google-chrome-stable"),
    "chromium": BrowserNames("chromium", "chromium"),
    "firefox": BrowserNames("firefox", "firefox"),
}


def _set_default_browser(browser_names: BrowserNames) -> None:
    run_shell_check(
        f"xdg-settings set default-web-browser {browser_names.name}.desktop"
        f"  && sudo update-alternatives --set x-www-browser /usr/bin/{browser_names.alt_name}"
        f"  && sudo update-alternatives --set gnome-www-browser /usr/bin/{browser_names.alt_name}"
    )


def register(app: typer.Typer) -> None:
    @app.command(name="browser")
    def browser_command(browser: str) -> None:
        result = rapidfuzz.process.extractOne(browser, KNOWN_BROWSERS.keys())
        if result is None:
            raise typer.BadParameter(
                f"Invalid value for browser. Choose from {KNOWN_BROWSERS.keys()}"
            )
        match, score, _ = result
        if score < 80:
            raise typer.BadParameter(
                f"Invalid value for browser. Choose from {KNOWN_BROWSERS.keys()}"
            )
        print(f"Setting default browser: {match}")
        _set_default_browser(KNOWN_BROWSERS[match])
