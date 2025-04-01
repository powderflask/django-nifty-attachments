import subprocess as sp
from pathlib import Path

from invoke import task

PROJECT_ROOT = Path(__file__).absolute().parent.parent


# more runners available at https://nektosact.com/usage/runners.html
@task(name="act")
def run_act(c, ubuntu_latest: str = "catthehacker/ubuntu:act-latest", args_str = None):
    args = [
        "act",
        "-C",
        f"{PROJECT_ROOT}",
        "--artifact-server-path",
        f"{PROJECT_ROOT}/.artifacts",
        *args_str.split(" ")
    ]
    if ubuntu_latest:
        args += ["-P", f"ubuntu-latest={ubuntu_latest}"]
    sp.run(args)
