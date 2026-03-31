import pathlib
import sqlite3

from migrations.run_migration import run_sql


def table_exists(db_path: pathlib.Path, table_name: str) -> bool:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None


def test_phase1_up_and_down_sql(tmp_path):
    db_path = tmp_path / "test.db"

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT)")
        conn.commit()

    # test file moved under test_suite/backend; migration SQL remains in backend/migrations
    base = pathlib.Path(__file__).resolve().parents[2]
    migration_dir = base / "backend" / "migrations"
    up_sql = (migration_dir / "001_phase1_up.sql").read_text(encoding="utf-8")
    down_sql = (migration_dir / "001_phase1_down.sql").read_text(encoding="utf-8")

    run_sql(db_path, up_sql)
    assert table_exists(db_path, "usage_counters")
    assert table_exists(db_path, "message_catalog")
    assert table_exists(db_path, "lesson_cards")
    assert table_exists(db_path, "profile_audit_log")

    run_sql(db_path, down_sql)
    assert not table_exists(db_path, "usage_counters")
    assert not table_exists(db_path, "message_catalog")
    assert not table_exists(db_path, "lesson_cards")
    assert not table_exists(db_path, "profile_audit_log")
    # Rollback should not remove pre-existing base tables.
    assert table_exists(db_path, "users")
