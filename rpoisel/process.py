from functools import partial
import subprocess

run_shell_check = partial(
    subprocess.run,
    check=True,
    shell=True,
    executable="/bin/bash",
)
