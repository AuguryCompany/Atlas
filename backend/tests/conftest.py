import os
import tempfile

import pytest

# Configure before the app module is imported anywhere.
_TMP = tempfile.mkdtemp(prefix="atlas-test-")
os.environ["ATLAS_DB_PATH"] = os.path.join(_TMP, "import.db")
os.environ["ATLAS_OFFLINE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from atlas.config import Settings  # noqa: E402
from atlas.main import create_app  # noqa: E402


def make_settings(tmp_path, **overrides) -> Settings:
    base = dict(db_path=tmp_path / "atlas.db", offline=True, auth_enabled=False)
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as c:
        yield c


@pytest.fixture
def auth_client(tmp_path):
    settings = make_settings(
        tmp_path,
        auth_enabled=True,
        api_keys={"view-key": "viewer", "analyst-key": "analyst", "admin-key": "admin"},
    )
    with TestClient(create_app(settings)) as c:
        yield c
