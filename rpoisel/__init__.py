from dataclasses import dataclass
import subprocess

import click
import rapidfuzz

from .util import AliasedGroup


@click.group(cls=AliasedGroup)
def cli() -> None:
    pass


@cli.command
@click.argument("variant", type=click.Choice(["1", "2", "2a"], case_sensitive=False))
def screen(variant: str) -> None:
    if variant == "1":
        subprocess.run(
            (
                "xrandr"
                " --output eDP-1 --primary --mode 1920x1080 --pos 0x0 --rate 60.02"
                " --output DP-1 --off"
            ),
            shell=True,
            check=True,
        )
    elif variant == "2":
        subprocess.run(
            (
                "xrandr"
                " --output eDP-1 --mode 1920x1080 --pos 3440x0 --rate 60.02"
                " --output DP-1 --primary --mode 3440x1440 --pos 0x0 --rate 29.99"
            ),
            shell=True,
            check=True,
        )
    elif variant == "2a":
        subprocess.run(
            (
                "xrandr"
                " --output eDP-1 --primary --mode 1920x1080 --pos 1920x0 --rate 60.02"
                " --output HDMI-1 --mode 1920x1080 --pos 0x0 --rate 29.99"
            ),
            shell=True,
            check=True,
        )


@cli.command
def sleep() -> None:
    subprocess.run("sync", shell=True)
    subprocess.run("sudo systemctl suspend", shell=True)


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
    subprocess.run(
        f"xdg-settings set default-web-browser {browser_names.name}.desktop",
        shell=True,
    )
    subprocess.run(
        f"sudo update-alternatives --set x-www-browser /usr/bin/{browser_names.alt_name}",
        shell=True,
    )
    subprocess.run(
        f"sudo update-alternatives --set gnome-www-browser /usr/bin/{browser_names.alt_name}",
        shell=True,
    )


@cli.command(name="browser")
@click.argument("browser", type=click.STRING)
def browser_command(browser: str) -> None:
    match, score, _ = rapidfuzz.process.extractOne(browser, KNOWN_BROWSERS.keys())
    if score < 80:
        raise click.BadParameter(
            f"Invalid value for 'browser. Choose from {KNOWN_BROWSERS.keys()}"
        )
    click.echo(f"Setting default browser: {match}")
    set_default_browser(KNOWN_BROWSERS[match])
