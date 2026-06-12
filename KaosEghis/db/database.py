from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
from pathlib import Path


APP_DIR_NAME = "KaosEghis"


def get_data_dir() -> Path:
    data_dir = Path.cwd() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    return get_data_dir() / "KaosEghis.sqlite"


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = path or get_database_path()
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(path: Path | None = None) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with connect(path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
