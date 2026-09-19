"""Points FTFM_DATA_DIR at a scratch directory before the app is imported, so no test touches a
real library."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["FTFM_DATA_DIR"] = tempfile.mkdtemp(prefix="ftfm-test-")
os.environ.pop("FTFM_BROWSER", None)


@pytest.fixture
def client():
    import app as appmod

    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()
