from dataclasses import dataclass

import click
import httpx
import rapidfuzz

from .util import AliasedGroup
from .process import run_shell_check
from .generator import ElispVisitor, visit_click_app


@click.group(cls=AliasedGroup)
def cli() -> None:
    pass


@cli.command
@click.argument("variant", type=click.Choice(["1", "2", "2a"], case_sensitive=False))
def screen(variant: str) -> None:
    if variant == "1":
        run_shell_check(
            (
                "xrandr"
                " --output eDP-1 --primary --mode 1920x1080 --pos 0x0 --rate 60.02"
                " --output DP-1 --off"
            ),
        )
    elif variant == "2":
        run_shell_check(
            (
                "xrandr"
                " --output eDP-1 --mode 1920x1080 --pos 3440x0 --rate 60.02"
                " --output DP-1 --primary --mode 3440x1440 --pos 0x0 --rate 29.99"
            ),
        )
    elif variant == "2a":
        run_shell_check(
            (
                "xrandr"
                " --output eDP-1 --primary --mode 1920x1080 --pos 1920x0 --rate 60.02"
                " --output HDMI-1 --mode 1920x1080 --pos 0x0 --rate 29.99"
            ),
        )
    run_shell_check(
        "awesome-client '(require(\"rc_util\")).arrange_clients_from_layout_config()'"
        '  && setxkbmap -layout "us,de" -option "grp:caps_toggle"'
    )


@cli.command
@click.argument("endpoint", type=click.Choice(["mic"], case_sensitive=False))
@click.argument("state", type=click.Choice(["on", "off"], case_sensitive=False))
def power(endpoint: str, state: str) -> None:
    if endpoint == "mic":
        httpx.post("http://192.168.87.67/relay/0", data={"turn": state})


@cli.command
def sleep() -> None:
    run_shell_check("sync")
    run_shell_check("sudo systemctl suspend")


@dataclass
class BrowserNames:
    name: str
    alt_name: str


KNOWN_BROWSERS: dict[str, BrowserNames] = {
    "chrome": BrowserNames("google-chrome", "google-chrome-stable"),
    "chromium": BrowserNames("chromium", "chromium"),
    "firefox": BrowserNames("firefox", "firefox"),
}


def set_default_browser(browser_names: BrowserNames) -> None:
    run_shell_check(
        f"xdg-settings set default-web-browser {browser_names.name}.desktop"
        f"  && sudo update-alternatives --set x-www-browser /usr/bin/{browser_names.alt_name}"
        f"  && sudo update-alternatives --set gnome-www-browser /usr/bin/{browser_names.alt_name}"
    )


@cli.command(name="browser")
@click.argument("browser", type=click.STRING)
def browser_command(browser: str) -> None:
    match, score, _ = rapidfuzz.process.extractOne(browser, KNOWN_BROWSERS.keys())
    if score < 80:
        raise click.BadParameter(
            f"Invalid value for browser. Choose from {KNOWN_BROWSERS.keys()}"
        )
    click.echo(f"Setting default browser: {match}")
    set_default_browser(KNOWN_BROWSERS[match])


@cli.command
def elisp() -> None:
    visitor = ElispVisitor()
    visit_click_app(cli, visitor)
    click.echo(visitor.spit())