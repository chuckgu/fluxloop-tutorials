from __future__ import annotations

import getpass
import os
from typing import Iterable


def ensure_env_vars(keys: Iterable[str]) -> None:
    for key in keys:
        if os.environ.get(key):
            continue
        os.environ[key] = getpass.getpass(f"{key}: ")

