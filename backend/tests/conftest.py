"""Aisla la base de datos de los tests en un archivo temporal.

Debe ejecutarse antes de importar ``app``: pytest carga conftest primero.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="nasa-space-tests-"))
os.environ["NASA_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
