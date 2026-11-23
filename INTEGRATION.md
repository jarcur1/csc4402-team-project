# Seed-bank integration checklist

Run this on one clean checkout before submission. Record the tested commit, Python and SQLite versions, fixed generator seed, reference date, query parameters, and the exact commands used. Compare query results before exercising CLI writes; use a disposable copy of the generated database for the CLI checks.

## 1. Prepare the handoff

- [ ] **Joseph and Jordan:** Review [PR #8](https://github.com/jarcur1/csc4402-team-project/pull/8). Confirm the [E-R diagram](design/er-diagram.pdf) matches the [SQLite contract](database/README.md), especially which lots count as available, which events deduct stock, and how replacement lots link to their grow-out. Resolve feedback before merging.
- [ ] **Luke and Owen:** Agree on a fixed seed, reference date, low-germination threshold, season bounds, and sample lot ID. Ensure the dataset covers the positive and negative cases in the query table below. Record expected rows and ordering in `queries/expected_results.md`.
- [ ] **Trey:** Map all four menus to `app/db.py`. Check that invalid counts, insufficient stock, and protected deletions produce understandable errors. Flag missing operations before the contract is finalized.

## 2. Build a fresh database

- [ ] From the repo root, run `python -m unittest discover -s tests -v`. All schema and inventory tests must pass, including rollback when the second line of a distribution fails.
- [ ] Run Luke’s documented `scripts/generate_data.py` command with the agreed seed and reference date against a new path. Generate only synthetic records. Confirm it fails rather than overwrites a database at an existing path.
- [ ] On the generated database, `PRAGMA integrity_check;` returns `ok`, `PRAGMA foreign_key_check;` returns no rows, and `SELECT lot_id FROM lot_stock WHERE on_hand_seeds < 0;` returns no rows.
- [ ] Generate again at another new path with the same inputs. The five ordered query results must match on both databases; byte-for-byte database equality is not required.

## 3. Verify the five queries

Run `queries/test_queries.sql` using Owen’s documented command and compare each result, including ordering, to `queries/expected_results.md`.

| Done | Query | Acceptance case |
| --- | --- | --- |
| ☐ | Low stock by variety | Include a variety with no lots and a positive target; held and retired lots do not count. A variety exactly at target is not low. |
| ☐ | Low germination by latest test | Two tests for the same lot share the latest date and straddle the threshold; the higher `test_id` wins. Untested lots are not reported as low. |
| ☐ | Most distributed by season | Sum quantities across multiple lots of one variety; omit out-of-season distributions and verify ranked order. |
| ☐ | Members who received a selected lot | Show each matching recipient, date, and quantity; exclude lines from other lots even if they are in the same distribution. |
| ☐ | Overdue grow-outs | Include open assignments due before the reference date. Exclude completed, cancelled, and open assignments due on or after that date. |

## 4. Exercise all four CLI workflows

Launch `app/cli.py` with Trey’s documented command against the disposable copy. Check the resulting rows and balances, not just the CLI messages.

| Done | Menu | Acceptance case |
| --- | --- | --- |
| ☐ | Lot intake and inventory | Receive a 10-seed lot and see 10 on hand. Mark it held: it still has 10 on hand but contributes zero available stock. Return it to available. |
| ☐ | Germination tests | Record a 3-seed sample drawn from stock and check the lot drops from 10 to 7. A test not drawn from stock leaves it at 7. A result with more germinated than tested is rejected without changes. |
| ☐ | Member distributions | With available lot balances of 7 and 2, post quantities of 4 and 3. The second line fails: balances stay 7 and 2, with no new header or item rows. Retry with 4 and 2: one header and two lines commit, and balances become 3 and 0. |
| ☐ | Grow-out coordination | Create an assignment: source stock stays at 3. Issue 2 seeds from a matching lot: stock falls to 1. Receive its replacement harvest as a new linked lot: the source stays at 1. |

- [ ] Try deleting a referenced grower or other protected record. Confirm the CLI reports why it was rejected and leaves the record intact.
- [ ] Save representative CLI output for the report, including the rejected distribution, and record any discrepancies with the tested commit and command.

## 5. Verify the submission package

- [ ] **Team:** Confirm all five contributions are integrated and the report credits actual work. Assemble one PDF (maximum eight pages, single-column, single-spaced, 11-point Arial) with the E-R figure, relational schema, query outcomes, and CLI illustrations.
- [ ] Package the populated database, schema, generator, SQL queries, CLI, tests, and exact run instructions in one ZIP. Unpack it into a clean folder and follow the included instructions against a fresh database before submitting.
