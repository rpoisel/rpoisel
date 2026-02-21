import json
import re
import sys
from enum import Enum
from pathlib import Path
from socket import AF_UNIX, SOCK_STREAM, socket
from typing import Any, Optional

import typer

from ..util.process import run_shell_check

# --- QEMU constants & helpers ---

QEMU_PID_FILES_BASE = Path("/") / "var" / "run"
QEMU_IMAGES_FILES_BASE = Path.home() / "images" / "hdimages"
QEMU_QMP_SOCKETS_BASE = Path("/") / "tmp"
QEMU_QMP_SOCKET_RE = re.compile(r"qmp-(.*)")


class QEMUError(Exception):
    pass


class QEMUVM:
    def __init__(self, name) -> None:
        self.name = name
        self.qmp_socket = _get_socket_path(name)
        try:
            self.pid = int(_get_pid_file_path(name).read_text().strip())
        except (FileNotFoundError, PermissionError) as exc:
            raise QEMUError(f"Could not instantiate QEMU VM {name}") from exc

    def __str__(self) -> str:
        return f"{self.name} ({self.pid}): {self.qmp_socket.resolve()}"


def _get_pid_file_path(name: str) -> Path:
    return QEMU_PID_FILES_BASE / f"qemu-{name}.pid"


def _get_socket_path(name: str) -> Path:
    return QEMU_QMP_SOCKETS_BASE / f"qmp-{name}"


def _create_image(name: str, size: str) -> Path:
    image_path = QEMU_IMAGES_FILES_BASE / f"{name}.vmdk"
    run_shell_check(f"qemu-img create -f vmdk {image_path} {size}")
    return image_path


def _list_vms() -> list[QEMUVM]:
    result: list[QEMUVM] = []
    for file in QEMU_QMP_SOCKETS_BASE.iterdir():
        if not file.is_socket():
            continue
        match = QEMU_QMP_SOCKET_RE.match(file.name)
        if not match:
            continue
        vm_name = match.group(1)
        try:
            result.append(QEMUVM(vm_name))
        except QEMUError as exc:
            print(f"Error interacting with VM: {exc}", file=sys.stderr)
            run_shell_check(f"sudo rm {_get_socket_path(vm_name)}")
            continue
    return result


# --- QMP client ---


class QMPClient:
    def __init__(self, qmp_socket: Path | str) -> None:
        self.__socket = socket(AF_UNIX, SOCK_STREAM)
        self.__socket.connect(
            str(qmp_socket) if isinstance(qmp_socket, Path) else qmp_socket
        )
        self.__sock_file = self.__socket.makefile(mode="r")
        self.__sock_file.readline()
        self.send_monitor_cmd("qmp_capabilities")

    def _read_parse_json(self) -> dict[str, Any]:
        return json.loads(self.__sock_file.readline().rstrip("\r\n"))

    def send_monitor_cmd(
        self, cmd: str, arguments: dict[str, str] = {}
    ) -> dict[str, Any]:
        self.__socket.sendall(
            (json.dumps({"execute": cmd, "arguments": arguments}) + "\n").encode()
        )
        response = self._read_parse_json()
        while response.get("event"):
            response = self._read_parse_json()
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["return"]


# --- VM command ---


class VMCommand(str, Enum):
    list = "list"
    create = "create"
    start = "start"
    state = "state"
    stop = "stop"
    cont = "cont"
    powerdown = "powerdown"


def register(app: typer.Typer) -> None:
    @app.command(name="vm")
    def vm_command(
        command: VMCommand,
        name: Optional[str] = typer.Argument(default=None),
        iso: Optional[Path] = typer.Option(None, help="Path to installation ISO"),
        size: str = typer.Option("20G", help="Disk image size"),
        vnc_display: int = typer.Option(0, help="VNC display number (port = 5900 + N)"),
        bridge: str = typer.Option(
            "bridge0", help="Network bridge to attach the VM to"
        ),
        force: bool = typer.Option(False, help="Overwrite existing disk image"),
    ) -> None:
        if command == VMCommand.list:
            for vm in _list_vms():
                print(str(vm))
            return

        if not name:
            typer.secho(
                "Error: missing argument 'name'.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        if command == VMCommand.create:
            if not iso:
                typer.secho(
                    "Error: --iso is required for 'create'.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(code=1)
            if not iso.exists():
                typer.secho(
                    f"Error: ISO file not found: {iso}",
                    fg=typer.colors.RED,
                    err=True,
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
            _create_image(name, size)
            qmp_socket_path = _get_socket_path(name)
            pid_file_path = _get_pid_file_path(name)
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

        qmp_socket_path = _get_socket_path(name)
        pid_file_path = _get_pid_file_path(name)
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
  -display vnc=:{vnc_display} \
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
