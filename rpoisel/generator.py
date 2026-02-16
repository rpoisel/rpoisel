from abc import ABC, abstractmethod
from typing import Union, override

import click


class Visitor(ABC):
    @abstractmethod
    def command(self, command: click.Command) -> None: ...


def visit_group(group: click.Group, visitor: Visitor, parent_name: str = "") -> None:
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            visit_group(command, visitor, parent_name + name + "-")
        else:
            visitor.command(command)


def visit_app(app: Union[click.Group, click.Command], visitor: Visitor) -> None:
    if isinstance(app, click.Group):
        visit_group(app, visitor)
    else:
        visitor.command(app)


class ElispVisitor(Visitor):
    def __init__(self) -> None:
        self._code: list[str] = []

    @override
    def command(self, command: click.Command) -> None:
        if command.name == "elisp":  # TODO determine command name from invoking command
            return
        self._code.append(f"(defun {command.name}-command ()")

        param_desc = "\n".join(
            [f"{param.name}, {param.type}" for param in command.params]
        )

        self._code.append(f"""  "Run the {command.name} command.

Parameters:
{param_desc}"
""")
        self._code.append("  (interactive)")
        self._code.append(f'  (shell-command "{command.name}"))')
        self._code.append("")

    def spit(self) -> str:
        return "\n".join(self._code).strip()
