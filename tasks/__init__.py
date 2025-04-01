from invoke import Collection

from . import clean, deps, docs, pypi, tox
from .utils import run_act

namespace = Collection(
    clean, deps, docs, tox, pypi, run_act
)