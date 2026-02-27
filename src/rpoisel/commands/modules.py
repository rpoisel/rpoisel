import getpass
import os
import platform
import subprocess
from enum import Enum
from pathlib import Path

import typer

MOK_PRIVATE_KEY = Path("/var/lib/shim-signed/mok/MOK.priv")
MOK_CERTIFICATE = Path("/var/lib/shim-signed/mok/MOK.der")


class ModulesCommand(str, Enum):
    sign = "sign"


def _sign_modules(modules_dir: Path, pattern: str, sign_file: Path) -> None:
    passphrase = getpass.getpass("Passphrase for the private key: ")
    env = {**os.environ, "KBUILD_SIGN_PIN": passphrase}
    matched = sorted(modules_dir.rglob(pattern))
    if not matched:
        typer.secho(
            f"No modules matching '{pattern}' in {modules_dir}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    for module_xz in matched:
        print(f"Signing {module_xz}")
        module_ko = module_xz.with_suffix("")  # strip .xz
        subprocess.run(["sudo", "xz", "-d", str(module_xz)], check=True)
        subprocess.run(
            [
                "sudo",
                "--preserve-env=KBUILD_SIGN_PIN",
                str(sign_file),
                "sha256",
                str(MOK_PRIVATE_KEY),
                str(MOK_CERTIFICATE),
                str(module_ko),
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                "sudo",
                "xz",
                "-f",
                "--check=crc32",
                "--lzma2=dict=512KiB",
                str(module_ko),
            ],
            check=True,
        )


def register(app: typer.Typer) -> None:
    @app.command(name="modules")
    def modules_command(
        command: ModulesCommand,
        pattern: str = typer.Argument(
            default="v4l2loopback*.ko.xz",
            help="Glob pattern to match module files (e.g. 'v4l2loopback*.ko.xz')",
        ),
    ) -> None:
        version = platform.release()
        modules_dir = Path(f"/lib/modules/{version}")
        kbuild_dir = Path(f"/usr/src/linux-headers-{version}")
        sign_file = kbuild_dir / "scripts" / "sign-file"

        if command == ModulesCommand.sign:
            _sign_modules(modules_dir, pattern, sign_file)
