import typer.main

from rpoisel import ElispVisitor, app, visit_app


def test_elisp_current() -> None:
    visitor = ElispVisitor()
    cli = typer.main.get_command(app)
    visit_app(cli, visitor)
    assert visitor.spit(), "at least something must be generated (for now)"
