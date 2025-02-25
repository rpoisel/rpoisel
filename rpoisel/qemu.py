import re
from pathlib import Path

import click

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
        except FileNotFoundError as exc:
            raise QEMUError(f"Could not instantiate QEMU VM {name}") from exc

    def __str__(self) -> str:
        return f"{self.name} ({self.pid}): {self.qmp_socket.resolve()}"


def get_pid_file_path(name: str) -> Path:
    return QEMU_PID_FILES_BASE / f"qemu-{name}.pid"


def get_socket_path(name: str) -> Path:
    return QEMU_QMP_SOCKETS_BASE / f"qmp-{name}"


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
            click.echo(f"Error interacting with VM: {exc}")
            run_shell_check(f"sudo rm {get_socket_path(vm_name)}")
            continue
    return result
