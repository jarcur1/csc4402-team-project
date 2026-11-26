# Application interfaces

**Status: Provisional.** The CLI is integrated with the SQLite contract in PR #8. Verification against the generated submission database is pending.

| Workflow | Tasks |
| --- | --- |
| Lot intake and inventory | Receive lots, check on-hand balances, change lot location or state, and record stock corrections. Maintain crops, varieties, growers, and storage locations. |
| Germination tests | View a lot's tests, record results with or without a stock sample, correct the germinated count, and delete tests that did not draw from stock. |
| Member distribution | Maintain member records and post or view distributions containing one or more lots. Posted distributions preserve their history. |
| Grow-out coordination | Plan and reschedule assignments, issue stock, receive a replacement harvest as a new lot, complete or cancel an assignment, and delete eligible unissued assignments. |

Blank input cancels the current action. Deletion requires confirmation. The CLI checks input format and displays database messages for constraints such as insufficient stock or protected records. Writes go through the shared operations in `app/db.py`.

## Launch

Run from the checkout root with Python 3.11+ and SQLite 3.37+. To open the populated submission database when available:

```powershell
python -m app.cli --database database/seedbank.db
```

For a scratch database, initialize a new file and use that path instead. Add crop, variety, grower, and storage location records in the inventory menu, then add a member in the distribution menu.

```powershell
python -m app.db database/seedbank-local.db
python -m app.cli --database database/seedbank-local.db
```

## Interface illustrations

```text
Community Seed Bank
1. Lot intake and inventory
2. Germination tests
3. Member distribution
4. Grow-out coordination
0. Exit
Choice:
```

In the scratch SQLite check, a two-lot distribution succeeded. A second attempt asked for 22 seeds from lot 2, which had 21 on hand. The CLI displayed the following response, and the database retained the same balances and distribution records.

```text
Post a distribution
Member ID (blank to cancel): 1
Distribution date (YYYY-MM-DD) (blank to cancel): 2026-11-12
Lot ID (blank to cancel): 1
Seeds issued (blank to cancel): 1
Add another lot? (y/n) (blank to cancel): y
Lot ID (blank to cancel): 2
Seeds issued (blank to cancel): 22
Add another lot? (y/n) (blank to cancel): n
Could not save. insufficient lot stock for distribution
```
