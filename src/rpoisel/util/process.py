import subprocess
import sys


def run_shell_check(args: str | list[str]) -> str:
    try:
        completed_process = subprocess.run(
            args,
            check=True,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
        )
        return completed_process.stdout
    except subprocess.CalledProcessError as exc:
        print(
            f"Problem (returncode={exc.returncode}): {exc.stdout} {exc.stderr}",
            file=sys.stderr,
        )
        raise
