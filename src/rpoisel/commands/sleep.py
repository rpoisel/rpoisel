import typer

from ..util.process import run_shell_check


def register(app: typer.Typer) -> None:
    @app.command()
    def sleep() -> None:
        run_shell_check("sync")
        run_shell_check("sudo systemctl suspend --force")
