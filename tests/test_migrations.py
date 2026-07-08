"""Alembic migration smoke test (offline, throwaway SQLite).

Guards against schema drift: verifies that ``alembic upgrade head`` builds every
table the SQLAlchemy ORM declares, and that ``downgrade base`` tears them down.
If a model is added/changed without a matching migration, this test (together
with ``alembic revision --autogenerate``) surfaces the gap.

Requires the ``alembic`` package (added to project deps in this step); the test
is skipped automatically if it is not installed.
"""
import pathlib
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

pytest.importorskip("alembic")
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402


def _make_config(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _expected_tables() -> set[str]:
    from src.core.db import Base
    from src.core import models  # noqa: F401  (registers tables)

    return set(Base.metadata.tables.keys())


def _tables_in(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_creates_all_orm_tables():
    db_path = pathlib.Path(tempfile.mkdtemp()) / "mig_up.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    command.upgrade(_make_config(db_url), "head")

    tables = _tables_in(db_url)
    missing = _expected_tables() - tables
    assert not missing, f"migration is missing ORM tables: {sorted(missing)}"


def test_downgrade_base_drops_orm_tables():
    db_path = pathlib.Path(tempfile.mkdtemp()) / "mig_down.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    cfg = _make_config(db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    leftover = _expected_tables() & _tables_in(db_url)
    assert not leftover, f"downgrade left ORM tables behind: {sorted(leftover)}"
