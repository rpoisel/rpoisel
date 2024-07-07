import subprocess


def run_shell_check(args: str | list[str]) -> str:
    completed_process = subprocess.run(
        args,
        check=True,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
    )
    return completed_process.stdout
