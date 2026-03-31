import argparse
import datetime as dt
import pathlib
import shutil
import sqlite3


def read_sql(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def backup_db(db_path: pathlib.Path) -> pathlib.Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".{stamp}.bak")
    shutil.copy2(db_path, backup_path)
    return backup_path


def run_sql(db_path: pathlib.Path, sql_text: str) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(sql_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase-1 DB migration scripts")
    parser.add_argument("direction", choices=["up", "down"], help="Migration direction")
    parser.add_argument("--db", required=True, help="Path to sqlite DB file")
    args = parser.parse_args()

    db_path = pathlib.Path(args.db).resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    migrations_dir = pathlib.Path(__file__).resolve().parent
    script_path = migrations_dir / ("001_phase1_up.sql" if args.direction == "up" else "001_phase1_down.sql")
    if not script_path.exists():
        print(f"Migration script not found: {script_path}")
        return 1

    backup_path = backup_db(db_path)
    print(f"Backup created: {backup_path}")

    sql_text = read_sql(script_path)
    run_sql(db_path, sql_text)
    print(f"Applied migration: {script_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
