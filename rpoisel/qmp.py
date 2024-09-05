import json
from pathlib import Path
from socket import AF_UNIX, SOCK_STREAM, socket
from typing import Any


class QMPClient:
    def __init__(self, qmp_socket: Path | str) -> None:
        self.socket = socket(AF_UNIX, SOCK_STREAM)
        self.socket.connect(
            str(qmp_socket) if isinstance(qmp_socket, Path) else qmp_socket
        )
        self.sock_file = self.socket.makefile(mode="r")
        self.sock_file.readline()
        self.send_monitor_cmd("qmp_capabilities")

    def _read_parse_json(self) -> dict[str, Any]:
        return json.loads(self.sock_file.readline().rstrip("\r\n"))

    def send_monitor_cmd(
        self, cmd: str, arguments: dict[str, str] = {}
    ) -> dict[str, Any]:
        self.socket.sendall(
            (json.dumps({"execute": cmd, "arguments": arguments}) + "\n").encode()
        )
        response = self._read_parse_json()
        while response.get("event"):
            response = self._read_parse_json()
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["return"]