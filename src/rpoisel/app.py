import typer

from .commands import browser, elisp, modules, power, screen, sleep, vm
from .commands import print as print_cmd
from .util.cli import AliasedGroup

app = typer.Typer(
    cls=AliasedGroup,
    name="rpoisel",
    help="Rainer Poisel personal CLI",
    no_args_is_help=True,
)

screen.register(app)
power.register(app)
sleep.register(app)
browser.register(app)
vm.register(app)
print_cmd.register(app)
modules.register(app)
elisp.register(app)
