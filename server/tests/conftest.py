"""Permite `import app...` ao rodar `pytest` de dentro de `server/`."""

import pathlib
import sys

SERVER_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
