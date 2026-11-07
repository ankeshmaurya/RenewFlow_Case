import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.loader import load_folder  # noqa: E402
from app.settings import Settings  # noqa: E402


@pytest.fixture(scope="session")
def tables():
    t, _ = load_folder(ROOT / "data" / "sample")
    return t


@pytest.fixture()
def settings():
    return Settings()
