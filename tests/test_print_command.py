import shlex
import subprocess
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from rpoisel import app


def test_print_from_path(monkeypatch, tmp_path: Path) -> None:
    commands: list[str] = []

    def fake_run_shell_check(command: str | list[str]) -> str:
        assert isinstance(command, str)
        commands.append(command)
        return ""

    monkeypatch.setattr("rpoisel.commands.print.run_shell_check", fake_run_shell_check)
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nsample\n")

    runner = CliRunner()
    result = runner.invoke(app, ["print", str(pdf_path), "-o", "number-up=2"])

    assert result.exit_code == 0
    assert commands == [
        f"scp {shlex.quote(str(pdf_path))} user@acme-vm:/tmp/",
        "ssh user@acme-vm 'lpr -P Samsung_M2020_Series -o number-up=2 /tmp/test.pdf'",
    ]


def test_print_from_stdin(monkeypatch) -> None:
    shell_commands: list[str] = []
    ssh_calls: list[dict[str, Any]] = []

    class FakeUUID:
        hex = "deadbeefcafebabe"

    def fake_run_shell_check(command: str | list[str]) -> str:
        assert isinstance(command, str)
        shell_commands.append(command)
        return ""

    def fake_subprocess_run(
        args: list[str], input: bytes, check: bool
    ) -> subprocess.CompletedProcess:
        ssh_calls.append({"args": args, "input": input, "check": check})
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("rpoisel.commands.print.run_shell_check", fake_run_shell_check)
    monkeypatch.setattr("rpoisel.commands.print.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("rpoisel.commands.print.uuid4", lambda: FakeUUID())

    runner = CliRunner()
    result = runner.invoke(
        app, ["print", "-o", "number-up=2"], input=b"%PDF-1.4\nsample\n"
    )

    assert result.exit_code == 0
    assert ssh_calls == [
        {
            "args": [
                "ssh",
                "user@acme-vm",
                "cat > /tmp/rpoisel-print-deadbeefcafebabe.pdf",
            ],
            "input": b"%PDF-1.4\nsample\n",
            "check": True,
        }
    ]
    assert shell_commands == [
        "ssh user@acme-vm 'set -euo pipefail; trap '\"'\"'rm -f /tmp/rpoisel-print-deadbeefcafebabe.pdf'\"'\"' EXIT; lpr -P Samsung_M2020_Series -o number-up=2 /tmp/rpoisel-print-deadbeefcafebabe.pdf'"
    ]


def test_print_path_rejects_non_pdf(monkeypatch, tmp_path: Path) -> None:
    def fake_run_shell_check(command: str | list[str]) -> str:
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("rpoisel.commands.print.run_shell_check", fake_run_shell_check)
    not_pdf_path = tmp_path / "not-pdf.txt"
    not_pdf_path.write_text("hello")

    runner = CliRunner()
    result = runner.invoke(app, ["print", str(not_pdf_path)])

    assert result.exit_code == 1
    assert "not a valid PDF" in result.output


def test_print_stdin_rejects_empty_input(monkeypatch) -> None:
    def fake_run_shell_check(command: str | list[str]) -> str:
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("rpoisel.commands.print.run_shell_check", fake_run_shell_check)

    runner = CliRunner()
    result = runner.invoke(app, ["print"], input=b"")

    assert result.exit_code == 1
    assert "no data received on stdin" in result.output
