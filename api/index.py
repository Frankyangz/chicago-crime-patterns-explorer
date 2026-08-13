"""Entry point for the Vercel Python runtime.

Vercel routes every request to this module (see vercel.json) rather than running
dashboard/app.py directly. Dash is a Flask application underneath, so exposing
that Flask instance as a module-level `app` is all the runtime needs: it serves
the WSGI callable it finds under that name.

Running locally is unchanged — `python dashboard/app.py` still works.
"""

from __future__ import annotations

import sys
from pathlib import Path

# dashboard/ is a plain directory rather than an installed package, so it has to
# be on the import path before `app` can be imported from it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from app import server as app  # noqa: E402
