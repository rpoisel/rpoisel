from enum import Enum

import typer

from ..util.process import run_shell_check


class ScreenVariant(str, Enum):
    one = "1"
    two = "2"
    three = "3"
    four = "4"


def register(app: typer.Typer) -> None:
    @app.command()
    def screen(variant: ScreenVariant) -> None:
        if variant == ScreenVariant.one:
            run_shell_check("autorandr --load one")
        elif variant == ScreenVariant.two:
            run_shell_check("autorandr --load two")
        elif variant == ScreenVariant.three:
            run_shell_check("autorandr --load three")
        elif variant == ScreenVariant.four:
            run_shell_check("autorandr --load four")
        run_shell_check(
            "awesome-client '(require(\"rc_util\")).arrange_clients_from_layout_config()'"
            '  && setxkbmap -layout "us,de" -option "grp:caps_toggle"'
        )
