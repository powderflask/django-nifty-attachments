from invoke import task
from pathlib import Path


@task
def test(ctx):
    """Run tests in the test-environment."""
    ctx.run("tox r -m test")


@task(aliases=("cov",))
def coverage(ctx):
    ctx.run("tox r coverage")


@task
def static(ctx):
    """Run all tox environments with a `static` label"""
    ctx.run("tox r -m static")


@task(aliases=("devenv",))
def venv(c, dir_name=".venv", force=False):
    """
    Initialize the development environment for this project.
    """
    if not force and Path(dir_name).exists():
        choice = input("The directory `.venv` already exists. Would you like to overwrite it? [y/N]\n")
        if choice.lower() != "y":
            return
    c.run(f"tox d -e dev {dir_name}")
