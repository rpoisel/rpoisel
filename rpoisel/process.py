from functools import partial
import subprocess

run_shell_check = partial(subprocess.run, shell=True, check=True)
