from pathlib import Path
from pprint import pprint

from invoke import task, Config


def require_docs_enabled(c):
    match c.config.docs.enabled:
        case True:
            return
        case False:
            print(
                "\033[33m"
                "This task requires `docs.enabled` to be set to `True`.",
                "To enable this task, set `docs.enabled: True` in your invoke.yaml file"
                "\033[0m"
            )
        case _:
            print(
                "\033[1;31mError:\033[0m Invalid value for `docs.enabled`.\n"
                f"Expected `True` or `False`, got: \033[32m{c.config.docs.enabled}\033[0m"
            )
    print("Exited with exit code 1")
    exit(1)


@task
def clean(c):
    """Clean up docs directory"""
    require_docs_enabled(c)
    with c.cd("docs"):
        c.run("make clean")


@task(clean)
def build(c):
    """Clean up and build Sphinx docs"""
    with c.cd("docs"):
        c.run("make html")


@task(build)
def release(c):
    """Push docs to GitHub, triggering webhook to build Read The Docs"""
    c.run("git push")

def mark_if_disabled(*tasks):
    _conf = Config(project_location=Path(__file__).parent.parent)
    _conf.load_project()
    if not _conf.docs.enabled:
        for func in tasks:
            func.__doc__ = "\033[31m[disabled]\033[0m " + func.__doc__

mark_if_disabled(clean, build, release)
