"""Seed-bank workflows for the shared SQLite contract in PR #8."""

import argparse
import sqlite3
from contextlib import closing
from datetime import date
from functools import partial
from pathlib import Path

from app import db


class Cancelled(Exception):
    pass


def integer(value, minimum):
    number = int(value)
    if number < minimum:
        raise ValueError(f"Enter an integer of at least {minimum}.")
    return number


def iso_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Enter a date in YYYY-MM-DD format.")
    return value


def one_of(*choices):
    def convert(value):
        if value.lower() not in choices:
            raise ValueError(f"Choose from {', '.join(choices)}.")
        return value.lower()

    return convert


def ask(label, convert=str):
    while True:
        value = input(f"{label} (blank to cancel): ").strip()
        if not value:
            raise Cancelled
        try:
            return convert(value)
        except ValueError as error:
            print(f"Invalid input. {error}")


def read_rows(conn, query, **params):
    return conn.execute(query, params).fetchall()


def list_action(label, query, **fields):
    return label, partial(read_rows, query=query), fields


def rename(conn, *, table, entry_id, name):
    db.rename_catalog_entry(conn, table, entry_id, name)


def delete(conn, *, table, entry_id):
    db.delete_catalog_entry(conn, table, entry_id)


POSITIVE = partial(integer, minimum=1)
NONNEGATIVE = partial(integer, minimum=0)
NAME = ("Name", str)
VARIETY = ("Variety ID", POSITIVE)
GROWER = ("Grower ID", POSITIVE)
LOCATION = ("Storage location ID", POSITIVE)
LOT = ("Lot ID", POSITIVE)
TEST = ("Test ID", POSITIVE)
ASSIGNMENT = ("Assignment ID", POSITIVE)
DUE = ("Due date (YYYY-MM-DD)", iso_date)
SEED_TARGET = ("Stock target in seeds", NONNEGATIVE)
HARVEST = ("Harvest date (YYYY-MM-DD)", iso_date)
RECEIVED = ("Receipt date (YYYY-MM-DD)", iso_date)
SEEDS_RECEIVED = ("Seeds received", POSITIVE)
LOT_STATUS = ("Lot state (available/held/retired)", one_of("available", "held", "retired"))


def catalog(label, table, key, add, **extra_fields):
    return (
        list_action(f"List {label} records", f"SELECT * FROM {table} ORDER BY {key}"),
        (f"Add {label}", add, {"name": NAME, **extra_fields}),
        (f"Rename {label}", partial(rename, table=table),
         {"entry_id": (f"{label.capitalize()} ID", POSITIVE), "name": NAME}),
        (f"Delete {label}", partial(delete, table=table),
         {"entry_id": (f"{label.capitalize()} ID", POSITIVE)}),
    )


def post_distribution(conn, *, member_id, distributed_on):
    items = []
    lot_ids = set()
    while True:
        lot_id = ask(*LOT)
        if lot_id in lot_ids:
            print("This lot is already on the distribution.")
            continue
        lot_ids.add(lot_id)
        items.append((lot_id, ask("Seeds issued", POSITIVE)))
        if ask("Add another lot? (y/n)", one_of("y", "n")) == "n":
            return db.post_distribution(conn, member_id=member_id,
                                        distributed_on=distributed_on, items=items)


def record_test(conn, *, sample_from_stock, **fields):
    if fields["seeds_germinated"] > fields["seeds_tested"]:
        raise ValueError("Seeds germinated cannot exceed seeds tested.")
    return db.record_test(conn, sample_from_stock=sample_from_stock == "y", **fields)


def revise_due_date(conn, *, assignment_id, due_on):
    row = conn.execute("SELECT source_lot_id FROM growout_assignment WHERE assignment_id = ?",
                       (assignment_id,)).fetchone()
    if row is None:
        raise ValueError("Grow-out assignment not found.")
    db.revise_growout(conn, assignment_id, due_on=due_on, source_lot_id=row["source_lot_id"])


def receive_replacement(conn, *, assignment_id, **fields):
    row = conn.execute("SELECT variety_id, grower_id FROM growout_assignment WHERE assignment_id = ?",
                       (assignment_id,)).fetchone()
    if row is None:
        raise ValueError("Grow-out assignment not found.")
    return db.receive_lot(conn, origin_assignment_id=assignment_id, **dict(row), **fields)


INVENTORY = (
    list_action("List seed lots", """
        SELECT s.lot_id, v.name AS variety, l.name AS location, s.lot_status, s.on_hand_seeds
        FROM lot_stock AS s
        JOIN seed_lot AS lot USING (lot_id)
        JOIN variety AS v ON v.variety_id = lot.variety_id
        JOIN storage_location AS l ON l.location_id = lot.location_id
        ORDER BY s.lot_id
    """),
    ("Receive a seed lot", db.receive_lot,
     dict(variety_id=VARIETY, grower_id=GROWER, location_id=LOCATION, harvested_on=HARVEST,
          received_on=RECEIVED, seeds_received=SEEDS_RECEIVED)),
    ("Change lot storage and state", db.update_lot_storage,
     dict(lot_id=LOT, location_id=LOCATION, lot_status=LOT_STATUS)),
    ("Record a stock adjustment", db.adjust_stock,
     dict(lot_id=LOT, adjusted_on=("Adjustment date (YYYY-MM-DD)", iso_date),
          delta_seeds=("Seeds to add or subtract (signed count)", int), reason=("Reason", str))),
    *catalog("crop", "crop", "crop_id", db.add_crop),
    *catalog("variety", "variety", "variety_id", db.add_variety,
             crop_id=("Crop ID", POSITIVE), stock_target_seeds=SEED_TARGET),
    ("Set variety stock target", db.set_stock_target,
     dict(variety_id=VARIETY, stock_target_seeds=SEED_TARGET)),
    *catalog("grower", "grower", "grower_id", db.add_grower),
    *catalog("storage location", "storage_location", "location_id", db.add_location),
)

TESTS = (
    list_action("List tests for a lot", """
        SELECT * FROM germination_test WHERE lot_id = :lot_id ORDER BY tested_on DESC, test_id DESC
    """, lot_id=LOT),
    ("Record a germination test", record_test,
     dict(lot_id=LOT, tested_on=("Test date (YYYY-MM-DD)", iso_date),
          seeds_tested=("Seeds tested", POSITIVE), seeds_germinated=("Seeds germinated", NONNEGATIVE),
          sample_from_stock=("Deduct tested seeds from stock? (y/n)", one_of("y", "n")))),
    ("Correct germinated count", db.correct_test_result,
     dict(test_id=TEST, seeds_germinated=("Seeds germinated", NONNEGATIVE))),
    ("Delete a test that did not use stock", db.delete_nonstock_test, dict(test_id=TEST)),
)

DISTRIBUTIONS = (
    list_action("List posted distributions", """
        SELECT d.distribution_id, m.name AS member, d.distributed_on, i.lot_id, i.seeds_issued
        FROM distribution AS d JOIN member AS m USING (member_id)
        JOIN distribution_item AS i USING (distribution_id)
        ORDER BY d.distribution_id, i.lot_id
    """),
    ("Post a distribution", post_distribution,
     dict(member_id=("Member ID", POSITIVE), distributed_on=("Distribution date (YYYY-MM-DD)", iso_date))),
    *catalog("member", "member", "member_id", db.add_member),
)

GROWOUTS = (
    list_action("List grow-out assignments", "SELECT * FROM growout_assignment ORDER BY assignment_id"),
    ("Plan a grow-out", db.create_growout,
     dict(variety_id=VARIETY, grower_id=GROWER, assigned_on=("Assignment date (YYYY-MM-DD)", iso_date),
          due_on=DUE)),
    ("Change a grow-out due date", revise_due_date, dict(assignment_id=ASSIGNMENT, due_on=DUE)),
    ("Issue seed for a grow-out", db.issue_growout,
     dict(assignment_id=ASSIGNMENT, source_lot_id=LOT, issued_on=("Issue date (YYYY-MM-DD)", iso_date),
          seeds_issued=("Seeds issued", POSITIVE))),
    ("Receive a replacement harvest", receive_replacement,
     dict(assignment_id=ASSIGNMENT, location_id=LOCATION, harvested_on=HARVEST,
          received_on=RECEIVED, seeds_received=SEEDS_RECEIVED)),
    ("Complete or cancel a grow-out", db.set_growout_status,
     dict(assignment_id=ASSIGNMENT, status=("New state (completed/cancelled)", one_of("completed", "cancelled")))),
    ("Delete an open, unissued grow-out", db.delete_growout, dict(assignment_id=ASSIGNMENT)),
)

MENUS = (
    ("Lot intake and inventory", INVENTORY),
    ("Germination tests", TESTS),
    ("Member distribution", DISTRIBUTIONS),
    ("Grow-out coordination", GROWOUTS),
)


def choose(title, labels, back):
    print(f"\n{title}")
    for number, label in enumerate(labels, 1):
        print(f"{number}. {label}")
    print(f"0. {back}")
    choices = {str(number): number for number in range(len(labels) + 1)}
    while True:
        value = input("Choice: ").strip()
        if value in choices:
            return choices[value]
        print("Choose a number from the menu.")


def run_action(conn, action):
    label, operation, fields = action
    print(f"\n{label}")
    try:
        arguments = {key: ask(*field) for key, field in fields.items()}
        if label.startswith("Delete") and ask("Confirm deletion? (y/n)", one_of("y", "n")) != "y":
            raise Cancelled
        result = operation(conn, **arguments)
    except Cancelled:
        print("Cancelled.")
    except sqlite3.IntegrityError as error:
        detail = str(error)
        if detail == "FOREIGN KEY constraint failed":
            detail = ("This record is referenced by other records." if label.startswith("Delete")
                      else "Check that the referenced IDs exist and match.")
        print(f"Could not save. {detail}")
    except (sqlite3.Error, ValueError, OverflowError) as error:
        print(f"Could not complete the operation. {error}")
    else:
        if isinstance(result, list):
            for row in result:
                print(" | ".join(f"{key}={row[key]}" for key in row.keys()))
            if not result:
                print("No records found.")
        elif result is None:
            print("Saved.")
        else:
            print(f"Saved as record {result}.")


def run(conn):
    try:
        while menu := choose("Community Seed Bank", [title for title, _ in MENUS], "Exit"):
            title, actions = MENUS[menu - 1]
            while action := choose(title, [entry[0] for entry in actions], "Back"):
                run_action(conn, actions[action - 1])
    except (EOFError, KeyboardInterrupt):
        print()
    print("Goodbye.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.exit(1, f"Database file not found: {args.database}\n")
    try:
        with closing(db.connect(args.database)) as conn:
            conn.execute("SELECT lot_id FROM lot_stock LIMIT 0")
            run(conn)
    except sqlite3.Error as error:
        parser.exit(1, f"Could not open the seed-bank database. {error}\n")


if __name__ == "__main__":
    main()
