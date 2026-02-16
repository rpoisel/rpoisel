from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
from pathlib import Path
from typing import Optional

import httpx
import rapidfuzz
import typer
import typer.main

from .generator import ElispVisitor, visit_app
from .process import run_shell_check
from .qemu import (
    QEMU_IMAGES_FILES_BASE,
    create_image,
    get_pid_file_path,
    get_socket_path,
    list_vms,
)
from .qmp import QMPClient
from .util import AliasedGroup


class ScreenVariant(str, Enum):
    one = "1"
    two = "2"
    three = "3"
    four = "4"


class PowerEndpoint(str, Enum):
    mic = "mic"
    other = "other"


class PowerState(str, Enum):
    on = "on"
    off = "off"


class VMCommand(str, Enum):
    list = "list"
    create = "create"
    start = "start"
    state = "state"
    stop = "stop"
    cont = "cont"
    powerdown = "powerdown"


app = typer.Typer(
    cls=AliasedGroup,
    name="rpoisel",
    help="Rainer Poisel personal CLI",
    no_args_is_help=True,
)


@app.command()
def screen(variant: ScreenVariant) -> None:
    if variant == ScreenVariant.one:
        run_shell_check("autorandr --load one")
    elif variant == ScreenVariant.two:
        run_shell_check("autorandr --load two")
    elif variant == ScreenVariant.three:
        run_shell_check("autorandr --load three")
    elif variant == ScreenVariant.four:
        run_shell_check("autorandr --load four")
    run_shell_check(
        "awesome-client '(require(\"rc_util\")).arrange_clients_from_layout_config()'"
        '  && setxkbmap -layout "us,de" -option "grp:caps_toggle"'
    )


@app.command()
def power(endpoint: PowerEndpoint, state: PowerState) -> None:
    IP_MAPPING: dict[PowerEndpoint, IPv4Address] = {
        PowerEndpoint.mic: IPv4Address("192.168.87.67"),
        PowerEndpoint.other: IPv4Address("192.168.87.18"),
    }
    ip = IP_MAPPING[endpoint]
    httpx.get(f"http://{ip}/relay/0?turn={state.value}")


@app.command()
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
    set_default_browser(KNOWN_BROWSERS[match])


@app.command(name="vm")
def vm_command(
    command: VMCommand,
    name: Optional[str] = typer.Argument(default=None),
    iso: Optional[Path] = typer.Option(None, help="Path to installation ISO"),
    size: str = typer.Option("20G", help="Disk image size"),
    vnc_display: int = typer.Option(0, help="VNC display number (port = 5900 + N)"),
    bridge: str = typer.Option("bridge0", help="Network bridge to attach the VM to"),
    force: bool = typer.Option(False, help="Overwrite existing disk image"),
) -> None:
    if command == VMCommand.list:
        for vm in list_vms():
            print(str(vm))
        return

    if not name:
        typer.secho("Error: missing argument 'name'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if command == VMCommand.create:
        if not iso:
            typer.secho(
                "Error: --iso is required for 'create'.", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1)
        if not iso.exists():
            typer.secho(
                f"Error: ISO file not found: {iso}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1)
        image_path = QEMU_IMAGES_FILES_BASE / f"{name}.vmdk"
        if image_path.exists() and not force:
            typer.secho(
                f"Error: image already exists: {image_path}. Use --force to overwrite.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        create_image(name, size)
        qmp_socket_path = get_socket_path(name)
        pid_file_path = get_pid_file_path(name)
        vnc_port = 5900 + vnc_display
        print(f"Creating VM '{name}' with {size} disk from {iso}")
        print(f"Connect via VNC to :{vnc_display} (port {vnc_port})")
        run_shell_check(f"""sudo qemu-system-x86_64 \
  -accel kvm \
  -cpu host \
  -m 4G \
  -netdev bridge,id=net0,br={bridge} \
  -device e1000,netdev=net0 \
  -netdev user,id=net1 \
  -device e1000,netdev=net1 \
  -drive file={image_path},format=vmdk,if=virtio \
  -cdrom {iso} \
  -boot d \
  -device usb-ehci,id=ehci \
  -device usb-host,vendorid=0x04e8,productid=0x3321 \
  -name qemu-vm-{name},process=vm-{name} \
  -display vnc=:{vnc_display} \
  -qmp unix:{qmp_socket_path},server=on,wait=off \
  -pidfile {pid_file_path}
""")
        return

    qmp_socket_path = get_socket_path(name)
    pid_file_path = get_pid_file_path(name)
    qmp_client = QMPClient(qmp_socket_path) if qmp_socket_path.exists() else None

    if command == VMCommand.state:
        if not qmp_client:
            print("QMP client not created. VM does not seem to run.")
            return
        result = qmp_client.send_monitor_cmd("query-status")
        print(result["status"])
    elif command == VMCommand.start:
        if qmp_client:
            print(f"VM {name} is already running.")
            return
        run_shell_check(f"""sudo qemu-system-x86_64 \
  -accel kvm \
  -cpu host \
  -m 4G \
  -netdev bridge,id=net0,br={bridge} \
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
  -qmp unix:{qmp_socket_path},server=on,wait=off \
  -pidfile {pid_file_path}
""")
        run_shell_check(f"""sudo chown $(id -u):$(id -g) {qmp_socket_path}""")
        run_shell_check(f"""sudo chown $(id -u):$(id -g) {pid_file_path}""")
    elif command == VMCommand.stop or command == VMCommand.cont:
        if not qmp_client:
            print("QMP client not created. VM does not seem to run.")
            return
        qmp_client.send_monitor_cmd(command.value)
    elif command == VMCommand.powerdown:
        if not qmp_client:
            print("QMP client not created. VM does not seem to run.")
            return
        qmp_client.send_monitor_cmd("system_powerdown")


@app.command()
def elisp() -> None:
    visitor = ElispVisitor()
    cli = typer.main.get_command(app)
    visit_app(cli, visitor)
    print(visitor.spit())
