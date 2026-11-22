"""Shared SQLite operations for the seed-bank generator and CLI."""

import argparse
from collections.abc import Iterable
from contextlib import closing
from itertools import chain
from pathlib import Path
import sqlite3

_SCHEMA = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
_CATALOG_KEYS = {
    "crop": "crop_id",
    "variety": "variety_id",
    "grower": "grower_id",
    "storage_location": "location_id",
    "member": "member_id",
}


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with named rows and no implicit transactions."""
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA recursive_triggers = ON")
    return db


def initialize(db: sqlite3.Connection) -> None:
    """Install the schema on a fresh connection, without replacing an existing schema."""
    if db.in_transaction:
        raise ValueError("initialize requires a connection with no active transaction")
    try:
        db.executescript(_SCHEMA.read_text(encoding="utf-8"))
    except BaseException:
        db.rollback()
        raise


def _insert(db, sql, parameters):
    return db.execute(sql, parameters).lastrowid


def _change(db, sql, parameters, error):
    if db.execute(sql, parameters).rowcount == 0:
        raise sqlite3.IntegrityError(error)


def add_crop(db, name: str) -> int:
    return _insert(db, "INSERT INTO crop (name) VALUES (?)", (name,))


def add_variety(db, *, crop_id: int, name: str, stock_target_seeds: int) -> int:
    return _insert(db, "INSERT INTO variety (crop_id, name, stock_target_seeds) VALUES (?, ?, ?)",
                   (crop_id, name, stock_target_seeds))


def add_grower(db, name: str) -> int:
    return _insert(db, "INSERT INTO grower (name) VALUES (?)", (name,))


def add_location(db, name: str) -> int:
    return _insert(db, "INSERT INTO storage_location (name) VALUES (?)", (name,))


def add_member(db, name: str) -> int:
    return _insert(db, "INSERT INTO member (name) VALUES (?)", (name,))


def rename_catalog_entry(db, table: str, entry_id: int, name: str) -> None:
    key = _CATALOG_KEYS[table]
    _change(db, f"UPDATE {table} SET name = ? WHERE {key} = ?", (name, entry_id), "catalog entry not found")


def delete_catalog_entry(db, table: str, entry_id: int) -> None:
    key = _CATALOG_KEYS[table]
    _change(db, f"DELETE FROM {table} WHERE {key} = ?", (entry_id,), "catalog entry not found")


def set_stock_target(db, variety_id: int, stock_target_seeds: int) -> None:
    _change(db, "UPDATE variety SET stock_target_seeds = ? WHERE variety_id = ?",
            (stock_target_seeds, variety_id), "variety not found")


def receive_lot(db, *, variety_id: int, grower_id: int, location_id: int, harvested_on: str,
                received_on: str, seeds_received: int, origin_assignment_id: int | None = None,
                lot_status: str = "available") -> int:
    return _insert(db, """
        INSERT INTO seed_lot (variety_id, grower_id, location_id, harvested_on, received_on,
                              seeds_received, origin_assignment_id, lot_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (variety_id, grower_id, location_id, harvested_on, received_on,
              seeds_received, origin_assignment_id, lot_status))


def update_lot_storage(db, lot_id: int, *, location_id: int, lot_status: str) -> None:
    _change(db, "UPDATE seed_lot SET location_id = ?, lot_status = ? WHERE lot_id = ?",
            (location_id, lot_status, lot_id), "lot not found")


def adjust_stock(db, *, lot_id: int, adjusted_on: str, delta_seeds: int, reason: str) -> int:
    return _insert(db, """
        INSERT INTO stock_adjustment (lot_id, adjusted_on, delta_seeds, reason) VALUES (?, ?, ?, ?)
        """, (lot_id, adjusted_on, delta_seeds, reason))


def record_test(db, *, lot_id: int, tested_on: str, seeds_tested: int, seeds_germinated: int,
                sample_from_stock: bool) -> int:
    return _insert(db, """
        INSERT INTO germination_test (lot_id, tested_on, seeds_tested, seeds_germinated, sample_from_stock)
        VALUES (?, ?, ?, ?, ?)
        """, (lot_id, tested_on, seeds_tested, seeds_germinated, sample_from_stock))


def correct_test_result(db, test_id: int, seeds_germinated: int) -> None:
    _change(db, "UPDATE germination_test SET seeds_germinated = ? WHERE test_id = ?",
            (seeds_germinated, test_id), "germination test not found")


def delete_nonstock_test(db, test_id: int) -> None:
    _change(db, "DELETE FROM germination_test WHERE test_id = ?", (test_id,), "germination test not found")


def post_distribution(db, *, member_id: int, distributed_on: str, items: Iterable[tuple[int, int]]) -> int:
    """Post one or more (lot_id, seeds_issued) pairs as an indivisible distribution."""
    lines = iter(items)
    try:
        first = next(lines)
    except StopIteration:
        raise sqlite3.IntegrityError("a distribution requires at least one item") from None

    db.execute("SAVEPOINT post_distribution")
    try:
        distribution_id = _insert(db, "INSERT INTO distribution (member_id, distributed_on) VALUES (?, ?)",
                                  (member_id, distributed_on))
        db.executemany("INSERT INTO distribution_item (distribution_id, lot_id, seeds_issued) VALUES (?, ?, ?)",
                       ((distribution_id, lot_id, quantity) for lot_id, quantity in chain((first,), lines)))
        db.execute("RELEASE post_distribution")
    except BaseException:
        db.execute("ROLLBACK TO post_distribution")
        db.execute("RELEASE post_distribution")
        raise
    return distribution_id


def create_growout(db, *, variety_id: int, grower_id: int, assigned_on: str, due_on: str,
                   source_lot_id: int | None = None) -> int:
    return _insert(db, """
        INSERT INTO growout_assignment (variety_id, grower_id, assigned_on, due_on, source_lot_id, status)
        VALUES (?, ?, ?, ?, ?, 'assigned')
        """, (variety_id, grower_id, assigned_on, due_on, source_lot_id))


def revise_growout(db, assignment_id: int, *, due_on: str, source_lot_id: int | None) -> None:
    _change(db, """
        UPDATE growout_assignment SET due_on = ?, source_lot_id = ? WHERE assignment_id = ?
        """, (due_on, source_lot_id, assignment_id), "grow-out assignment not found")


def issue_growout(db, assignment_id: int, *, source_lot_id: int, issued_on: str, seeds_issued: int) -> None:
    _change(db, """
        UPDATE growout_assignment
        SET source_lot_id = ?, issued_on = ?, seeds_issued = ?, status = 'in_progress'
        WHERE assignment_id = ? AND issued_on IS NULL AND status IN ('assigned', 'in_progress')
        """, (source_lot_id, issued_on, seeds_issued, assignment_id), "no open, unissued grow-out with that ID")


def set_growout_status(db, assignment_id: int, status: str) -> None:
    _change(db, "UPDATE growout_assignment SET status = ? WHERE assignment_id = ?",
            (status, assignment_id), "grow-out assignment not found")


def delete_growout(db, assignment_id: int) -> None:
    _change(db, "DELETE FROM growout_assignment WHERE assignment_id = ?",
            (assignment_id,), "grow-out assignment not found")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a new seed-bank SQLite database.")
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        with args.database.open("xb"):
            pass
        with closing(connect(args.database)) as db:
            initialize(db)
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")
    print(f"Initialized {args.database}")


if __name__ == "__main__":
    _main()
