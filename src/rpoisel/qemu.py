import re
import sys
from pathlib import Path

from .process import run_shell_check

QEMU_PID_FILES_BASE = Path("/") / "var" / "run"
QEMU_IMAGES_FILES_BASE = Path.home() / "images" / "hdimages"
QEMU_QMP_SOCKETS_BASE = Path("/") / "tmp"
QEMU_QMP_SOCKET_RE = re.compile(r"qmp-(.*)")


class QEMUError(Exception):
    pass


class QEMUVM:
    def __init__(self, name) -> None:
        self.name = name
        self.qmp_socket = get_socket_path(name)
        try:
            self.pid = int(get_pid_file_path(name).read_text().strip())
        except (FileNotFoundError, PermissionError) as exc:
            raise QEMUError(f"Could not instantiate QEMU VM {name}") from exc

    def __str__(self) -> str:
        return f"{self.name} ({self.pid}): {self.qmp_socket.resolve()}"


def get_pid_file_path(name: str) -> Path:
    return QEMU_PID_FILES_BASE / f"qemu-{name}.pid"


def get_socket_path(name: str) -> Path:
    return QEMU_QMP_SOCKETS_BASE / f"qmp-{name}"


def create_image(name: str, size: str) -> Path:
    image_path = QEMU_IMAGES_FILES_BASE / f"{name}.vmdk"
    run_shell_check(f"qemu-img create -f vmdk {image_path} {size}")
    return image_path


def list_vms() -> list[QEMUVM]:
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
            run_shell_check(f"sudo rm {get_socket_path(vm_name)}")
            continue
    return result
