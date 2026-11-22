# Seed-bank SQLite contract

## Initialize and check

Run these from the repository root with Python 3.11+ and SQLite 3.37+ (the version linked to Python is available as `sqlite3.sqlite_version`). No third-party packages are required.

```sh
python -m app.db database/seedbank-local.db
python -m unittest discover -s tests -v
```

The initialization command refuses an existing path. `seedbank-local.db` is a scratch database; `database/seedbank.db` is reserved for the populated submission. The integrity tests create their own databases. For code that initializes a new database, call `db.initialize(conn)` on an idle connection; use `with contextlib.closing(db.connect(path)) as conn:` to close it.

## Report section: Relational schema and integrity

The schema implements the [E-R model](../design/er-model.md) as eleven relations. Crop names and storage-location names are unique; variety names are unique within a crop. Each physical lot references one variety, grower, and location; an optional grow-out link records the origin of replacement harvests. A distribution header identifies the recipient and date, and its lines are keyed by distribution and lot. Germination tests and stock adjustments reference one lot; an assignment's optional source references a lot of the same variety. Foreign keys restrict deletion of referenced rows.

Stock is derived, not stored as a second editable counter. The lot balance is intake minus distribution quantities, stock samples, and issued grow-out quantities, plus signed adjustments. Only available lots contribute to variety availability. Database constraints reject invalid counts, dates, references, and stock changes that would overdraw a lot. The shared posting operation writes a nonempty distribution and all its items in one transaction; if any item fails, none of them are recorded. Corrections to posted quantities are explicit adjustment records, so posting history remains visible.

## Tables and read views

`PK` = primary key, `FK` = foreign key, `?` = nullable. All other columns are required. IDs and seed counts are integers. Supply dates as `YYYY-MM-DD`. The database rejects impossible dates. Row names are case-sensitive for uniqueness.

| Table | Columns |
| --- | --- |
| `crop` | `crop_id` PK, `name` |
| `variety` | `variety_id` PK, `crop_id` FK, `name`, `stock_target_seeds` (nonnegative) |
| `grower` | `grower_id` PK, `name` |
| `storage_location` | `location_id` PK, `name` |
| `member` | `member_id` PK, `name` |
| `seed_lot` | `lot_id` PK, `variety_id` FK, `grower_id` FK, `location_id` FK, `origin_assignment_id` FK?, `harvested_on`, `received_on`, `seeds_received`, `lot_status` |
| `germination_test` | `test_id` PK, `lot_id` FK, `tested_on`, `seeds_tested`, `seeds_germinated`, `sample_from_stock` (`0` or `1`) |
| `distribution` | `distribution_id` PK, `member_id` FK, `distributed_on` |
| `distribution_item` | `distribution_id` FK + `lot_id` FK (composite PK), `seeds_issued` |
| `growout_assignment` | `assignment_id` PK, `variety_id` FK, `grower_id` FK, `source_lot_id` FK?, `assigned_on`, `due_on`, `issued_on`?, `seeds_issued`?, `status` |
| `stock_adjustment` | `adjustment_id` PK, `lot_id` FK, `adjusted_on`, signed nonzero `delta_seeds`, `reason` |

- `lot_stock(lot_id, variety_id, lot_status, on_hand_seeds)` gives the current balance of each lot, including held and retired lots. The event dates are business dates, not an as-of balance API.
- `variety_stock(variety_id, stock_target_seeds, available_seeds)` includes **every** variety, even if it has no available lots. For insufficient stock, filter `available_seeds < stock_target_seeds`.
- For latest germination, order per lot by `tested_on DESC, test_id DESC`; there is no measured rate for an untested lot. Use real division for the rate. For seasonal rankings, filter distribution dates before totaling item quantities by the source lot's `variety_id`. For recipients, start from items for the specified `lot_id`. Overdue means `due_on < :reference_date` and status `assigned` or `in_progress`.

## Shared write API (`app.db`)

First argument is an open connection from `connect(path)`, except for `connect` itself. It enables foreign-key enforcement and recursive triggers; callers should not turn either off. Query the views/tables with parameterized `SELECT`s; rows support column names. Write through this API, particularly distributions: SQLite enforces item constraints, but the operation enforces that a header cannot be posted without items. Each operation is atomic; within an explicit caller transaction, `post_distribution` rolls back only its own work on failure. Invalid domain values or references raise `sqlite3.IntegrityError`. Creation operations return the new integer ID; updates and deletes return `None`.

| Operation | Arguments after `conn` |
| --- | --- |
| `add_crop`, `add_grower`, `add_location`, `add_member` | `name` |
| `add_variety` | `*, crop_id, name, stock_target_seeds` |
| `rename_catalog_entry`, `delete_catalog_entry` | `table, entry_id, name` (omit `name` for deletion); `table` is one of `crop`, `variety`, `grower`, `storage_location`, `member` |
| `set_stock_target` | `variety_id, stock_target_seeds` |
| `receive_lot` | `*, variety_id, grower_id, location_id, harvested_on, received_on, seeds_received, origin_assignment_id=None, lot_status='available'` |
| `update_lot_storage` | `lot_id, *, location_id, lot_status` |
| `adjust_stock` | `*, lot_id, adjusted_on, delta_seeds, reason` |
| `record_test` | `*, lot_id, tested_on, seeds_tested, seeds_germinated, sample_from_stock` |
| `correct_test_result`, `delete_nonstock_test` | `test_id, seeds_germinated` (omit `seeds_germinated` for deletion) |
| `post_distribution` | `*, member_id, distributed_on, items` (one or more distinct `(lot_id, seeds_issued)` pairs) |
| `create_growout` | `*, variety_id, grower_id, assigned_on, due_on, source_lot_id=None` |
| `revise_growout` | `assignment_id, *, due_on, source_lot_id` (pass the existing source after issuance) |
| `issue_growout` | `assignment_id, *, source_lot_id, issued_on, seeds_issued` |
| `set_growout_status`, `delete_growout` | `assignment_id, status` (omit `status` for deletion) |

Initialize data in dependency order: crop before variety; variety, grower and location before seed lots; member and lots before distributions; lot before its tests or adjustments; variety and grower before creating an assignment. An assignment can be planned without a source. Issue it from an `available` lot of its variety, then receive any resulting harvests as distinct new lots of the same variety and grower. Test, adjustment, distribution, and issue dates cannot precede the lot's receipt date.

- **Lot states:** `available`, `held`, `retired`. Only `available` lots can be used for new distributions or grow-out issues. Retire rather than delete lots. Record stock corrections with `adjust_stock`; posted receipts, distribution lines, test debits, grow-out issues, and adjustments are not rewritten or deleted.
- **Test maintenance:** A test only deducts seeds when `sample_from_stock=True`. The germinated count can be corrected in either case. Only non-stock tests can be deleted.
- **Grow-out states:** Starts `assigned`; `issue_growout` records a positive issue exactly once, setting `in_progress`. `completed` requires a recorded issue. `cancelled` may have an issue; cancelling never puts stock back. Completed and cancelled records are read-only. Only open, unissued assignments may be deleted.
