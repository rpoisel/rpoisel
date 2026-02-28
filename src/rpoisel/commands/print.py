import shlex
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import typer

from ..util.process import run_shell_check

REMOTE_HOST = "user@acme-vm"
REMOTE_TMP_DIR = "/tmp"
REMOTE_PRINTER = "Samsung_M2020_Series"


def _is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def _read_pdf(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        typer.secho(
            f"Error: file not found: {path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    data = path.read_bytes()
    if not _is_pdf(data):
        typer.secho(
            f"Error: file is not a valid PDF: {path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    return data


def _build_remote_print_cmd(
    remote_path: str, extra_args: list[str], cleanup: bool
) -> str:
    lpr_cmd = " ".join(
        shlex.quote(part)
        for part in ["lpr", "-P", REMOTE_PRINTER, *extra_args, remote_path]
    )
    if not cleanup:
        return lpr_cmd
    return f"set -euo pipefail; trap 'rm -f {shlex.quote(remote_path)}' EXIT; {lpr_cmd}"


def _print_from_path(path: Path, extra_args: list[str]) -> None:
    _read_pdf(path)
    run_shell_check(f"scp {shlex.quote(str(path))} {REMOTE_HOST}:{REMOTE_TMP_DIR}/")
    remote_path = f"{REMOTE_TMP_DIR}/{path.name}"
    remote_cmd = _build_remote_print_cmd(remote_path, extra_args, cleanup=False)
    run_shell_check(f"ssh {REMOTE_HOST} {shlex.quote(remote_cmd)}")


def _print_from_stdin(extra_args: list[str]) -> None:
    if sys.stdin.isatty():
        typer.secho(
            "Error: either provide a PDF path or pipe PDF data via stdin.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    data = sys.stdin.buffer.read()
    if not data:
        typer.secho(
            "Error: no data received on stdin.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if not _is_pdf(data):
        typer.secho(
            "Error: stdin data is not a valid PDF.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    remote_path = f"{REMOTE_TMP_DIR}/rpoisel-print-{uuid4().hex}.pdf"
    subprocess.run(
        ["ssh", REMOTE_HOST, f"cat > {shlex.quote(remote_path)}"],
        input=data,
        check=True,
    )
    remote_cmd = _build_remote_print_cmd(remote_path, extra_args, cleanup=True)
    run_shell_check(f"ssh {REMOTE_HOST} {shlex.quote(remote_cmd)}")


def _parse_args(args: list[str]) -> tuple[Path | None, list[str]]:
    if not args:
        return None, []
    if args[0] == "--":
        return None, args[1:]
    if args[0].startswith("-"):
        return None, args
    return Path(args[0]), args[1:]


def register(app: typer.Typer) -> None:
    @app.command(
        name="print",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def print_command(ctx: typer.Context) -> None:
        path, extra_args = _parse_args(ctx.args)
        if path:
            _print_from_path(path, extra_args)
            return
        _print_from_stdin(extra_args)
