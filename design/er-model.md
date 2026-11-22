# Seed-bank E-R model

## Report section: Entity–relationship design

**Figure — Seed-bank entity–relationship diagram.** [Report-ready PDF](er-diagram.pdf) · [Editable diagrams.net source](er-diagram.drawio)

The model distinguishes a crop, its named varieties, and the physical seed lots held by the bank. Two lots of the same variety can have different growers, harvest dates, locations, and germination histories. A member distribution contains one or more line items. Each item names the lot used and the quantity issued, preserving traceability even when one distribution draws from several lots.

Each grow-out assignment names a grower and a variety. It can be planned before a source lot is selected. Posting an issue consumes seeds from one existing lot of that variety. The resulting harvests enter inventory as new lots linked to the assignment; they do not replenish the original lot in place. Stock is tracked in whole seeds per lot. The bank compares the sum of stock in distributable lots with the target for each variety, including varieties with no distributable lots.

## Entity and attribute dictionary

Fields are required unless marked optional. `ID` fields are stable primary keys unless another key is specified. Foreign keys point to the named entities. Dates are calendar dates; counts are integers.

| Entity | Attributes and meaning |
| --- | --- |
| Crop | `crop_id`, `name`: crop identity and display name. |
| Variety | `variety_id`, `crop_id`, `name`, `stock_target_seeds`: named variety within one crop and its minimum desired available stock (nonnegative). |
| Grower | `grower_id`, `name`: contributor of harvested lots and recipient of grow-out assignments. |
| Storage Location | `location_id`, `name`: labeled place where a lot is tracked. A retired lot retains its last recorded location. |
| Seed Lot | `lot_id`, `variety_id`, `grower_id`, `location_id`, optional `origin_assignment_id`, `harvested_on`, `received_on`, `seeds_received`, `lot_status`: one physical intake with a positive initial seed count; status is `available`, `held`, or `retired`. |
| Germination Test | `test_id`, `lot_id`, `tested_on`, `seeds_tested`, `seeds_germinated`, `sample_from_stock`: a dated result; the flag says whether the tested seeds came out of recorded stock. |
| Member | `member_id`, `name`: recipient identity and display name. |
| Distribution | `distribution_id`, `member_id`, `distributed_on`: one dated issuance to one member. |
| Distribution Item | `distribution_id`, `lot_id`, `seeds_issued`: positive quantity drawn from one lot. The pair `(distribution_id, lot_id)` is both the primary key and two foreign keys, so each lot appears at most once in a distribution. |
| Grow-out Assignment | `assignment_id`, `variety_id`, `grower_id`, optional `source_lot_id`, `assigned_on`, `due_on`, optional `issued_on`, optional `seeds_issued`, `status`: a regeneration assignment. Status is `assigned`, `in_progress`, `completed`, or `cancelled`; completed and cancelled are terminal and are not overdue. |
| Stock Adjustment | `adjustment_id`, `lot_id`, `adjusted_on`, `delta_seeds`, `reason`: a dated correction with a nonzero signed quantity and a reason. |

## Business rules for the schema handoff

- **Stock:** Derive a lot’s balance from seeds received, less distribution items, less germination samples drawn from stock, less posted grow-out issues, plus signed adjustments. Do not maintain an independent editable balance. Only lots in `available` status can supply new distributions or grow-out issues. Held and retired lots do not count toward the variety target. An eligible lot with no remaining stock contributes zero.
- **Atomic posting:** Reject operations that would make any lot’s balance negative. A posted distribution contains at least one item; commit the header and all items together. Record quantity corrections explicitly as adjustments rather than rewriting posted inventory history.
- **Germination:** Require `seeds_tested > 0` and `0 ≤ seeds_germinated ≤ seeds_tested`. When `sample_from_stock` is true, deduct exactly `seeds_tested`; otherwise deduct nothing. Use `(tested_on, test_id)` descending for the latest result so same-day tests have a stable tie-breaker.
- **Grow-outs:** `due_on` cannot precede `assigned_on`. A selected source lot must match the assignment’s variety. `issued_on` and a positive `seeds_issued` are recorded together when stock leaves the bank, never before `assigned_on`; both are absent before issuance. Posting requires a source lot. Once issued, the source and issue are retained even if the assignment is cancelled. A resulting lot must be a new intake, match the assignment’s variety and grower, and be harvested on or after the recorded issue date. An assignment may yield no harvest or several, but uses at most one source lot.
- **Intake and history:** `received_on` cannot precede `harvested_on`. Every lot has one grower, one variety, and one storage location. Only lots harvested through an assignment reference an originating assignment. Protect referenced history from deletion.

## Workflow and query coverage

| Workflow or query | Model path |
| --- | --- |
| Lot intake and inventory | Crop → Variety → Seed Lot; Grower and Storage Location identify intake; Stock Adjustment records corrections. |
| Germination entry | Seed Lot → Germination Test; the test carries its date, counts, and stock-sample flag. |
| Member distributions | Member → Distribution → Distribution Item → Seed Lot; the line identifies what left inventory. |
| Grow-out coordination | Grower and Variety → Grow-out Assignment; a source lot supplies the issue; new lots keep the assignment as their origin. |
| Insufficient stock | Start with every Variety, sum only balances of available lots (zero if none), and compare against `stock_target_seeds`. |
| Low germination | Use the latest Germination Test per lot and compare its germination fraction with the query threshold; lots without tests have no measured rate. |
| Most distributed by season | Filter Distribution dates to the selected season, then sum Distribution Item quantities by the Variety of each source lot. |
| Members who received a given lot | Filter Distribution Items by lot, then join to Distribution and Member for dates, quantities, and recipients. |
| Overdue grow-outs | Select assignments with `due_on` before the reference date and status `assigned` or `in_progress`. |

Open `er-diagram.drawio` in diagrams.net to edit the figure; re-export the PDF when the model changes. The SQL schema in [issue #3](https://github.com/jarcur1/csc4402-team-project/issues/3) should be checked against these rules before the team submits the report.
