from enum import Enum
from ipaddress import IPv4Address

import httpx
import typer


class PowerEndpoint(str, Enum):
    mic = "mic"
    other = "other"


class PowerState(str, Enum):
    on = "on"
    off = "off"


def register(app: typer.Typer) -> None:
    @app.command()
    def power(endpoint: PowerEndpoint, state: PowerState) -> None:
        IP_MAPPING: dict[PowerEndpoint, IPv4Address] = {
            PowerEndpoint.mic: IPv4Address("192.168.87.67"),
            PowerEndpoint.other: IPv4Address("192.168.87.18"),
        }
        ip = IP_MAPPING[endpoint]
        httpx.get(f"http://{ip}/relay/0?turn={state.value}")
