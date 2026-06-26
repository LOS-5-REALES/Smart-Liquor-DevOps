import os
import sys

import pytest

# app/ usa imports planos (import models, from database import Base),
# asi que necesita estar en sys.path para que los tests puedan importarlo.
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# database.py crea el engine al importarse (a nivel de modulo), asi que
# DATABASE_URL debe existir antes del import o create_engine(None) explota.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import models  # noqa: E402

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture()
def db():
    """Sesion de DB aislada por test, con tablas frescas en SQLite en memoria."""
    models.Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=TEST_ENGINE)
