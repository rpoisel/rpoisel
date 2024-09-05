from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path

import click
import httpx
import rapidfuzz

from .generator import ElispVisitor, visit_click_app
from .process import run_shell_check
from .qmp import QMPClient
from .util import AliasedGroup


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
@click.argument("endpoint", type=click.Choice(["mic", "other"], case_sensitive=False))
@click.argument("state", type=click.Choice(["on", "off"], case_sensitive=False))
def power(endpoint: str, state: str) -> None:
    IP_MAPPING: dict[str, IPv4Address] = {
        "mic": IPv4Address("192.168.87.67"),
        "other": IPv4Address("192.168.87.18"),
    }
    ip = IP_MAPPING[endpoint]
    httpx.get(f"http://{ip}/relay/0?turn={state}")


@cli.command
def sleep() -> None:
    run_shell_check("sync")
    run_shell_check("sudo systemctl suspend --force")


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


QEMU_PID_FILES_BASE = Path("/") / "var" / "run"
QEMU_IMAGES_FILES_BASE = Path.home() / "images" / "hdimages"


@cli.command(name="vm")
@click.argument(
    "command",
    type=click.Choice(
        ["start", "state", "stop", "cont", "powerdown"], case_sensitive=False
    ),
)
@click.argument("name", type=click.STRING)
def vm_command(name: str, command: str) -> None:
    pid_file = QEMU_PID_FILES_BASE / f"qemu-{name}.pid"
    qmp_socket = Path("/") / "tmp" / f"qmp-sock-{name}"
    qmp_client = QMPClient(qmp_socket) if qmp_socket.exists() else None

    if command == "state":
        if not qmp_client:
            click.echo("QMP client not created. VM does not seem to run.")
            return
        result = qmp_client.send_monitor_cmd("query-status")
        click.echo(result["status"])
    elif command == "start":
        if qmp_client:
            click.echo(f"VM {name} is already running.")
            return
        run_shell_check(f"""sudo qemu-system-x86_64 \
  -accel kvm \
  -cpu host \
  -m 4G \
  -netdev bridge,id=net0,br=bridge0 \
  -device e1000,netdev=net0 \
  -netdev user,id=net1 \
  -device e1000,netdev=net1 \
  -drive file={QEMU_IMAGES_FILES_BASE}/{name}.vmdk,format=vmdk,if=virtio \
  -device usb-ehci,id=ehci \
  -device usb-host,vendorid=0x04e8,productid=0x3321 \
  -name qemu-vm-{name},process=vm-{name} \
  -daemonize \
  -serial none \
  -display none \
  -qmp unix:{qmp_socket},server=on,wait=off \
  -pidfile {pid_file}
""")
        run_shell_check(f"""sudo chown $(id -u):$(id -g) {qmp_socket}""")
    elif command == "stop" or command == "cont":
        if not qmp_client:
            click.echo("QMP client not created. VM does not seem to run.")
            return
        qmp_client.send_monitor_cmd(command)
    elif command == "powerdown":
        if not qmp_client:
            click.echo("QMP client not created. VM does not seem to run.")
            return
        qmp_client.send_monitor_cmd("system_powerdown")


@cli.command
def elisp() -> None:
    visitor = ElispVisitor()
    visit_click_app(cli, visitor)
    click.echo(visitor.spit())
