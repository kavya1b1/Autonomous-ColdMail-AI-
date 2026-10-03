"""Backward-compatible schema import module.

The canonical definitions live in ``models.schemas`` (the package directory).
This file is retained for tooling that discovers a module at this path.
"""
from models.schemas import *  # noqa: F401,F403
