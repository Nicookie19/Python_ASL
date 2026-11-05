"""Make the source package importable from either supported pytest cwd."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Every test gets a private database; running the suite must never modify a learner's data.
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    from app.data import db
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    db.init_db()
    yield
    conn = getattr(db._thread_local, "conn", None)
    if conn is not None:
        conn.close()
        db._thread_local.conn = None
