# CSC4402: Community Seed Bank & Regeneration Cooperative

Five-person database project for a local nonprofit that collects, tests, stores, distributes, and regenerates seeds.

**Decision: We are building the seed bank project. Enterprise selection is complete.**

## Assignment requirements

The enterprise must justify a relational database while remaining small enough to complete during the semester.

The five project parts are:

1. **E-R diagram:** Entities, attributes, relationships, keys, and cardinalities.
2. **Relational schema:** Tables and constraints that correctly implement the E-R model.
3. **Data generation:** A populated database and the script used to generate synthetic data.
4. **Test queries:** Five executable queries with sample/expected results.
5. **Application interfaces:** Up to five interfaces for input, updates, and deletion across different user tasks. CLI interfaces are acceptable.

Submission also requires a report of no more than eight pages, participation details, database/application/test code, and execution instructions. SQLite or MySQL is recommended in the assignment.

**Deadline clarification needed:** The supplied description says Fall 2026 but lists a December 1, 2024 deadline. Confirm the current deadline with the instructor.

## Selected enterprise

The seed bank was selected for its distinct entities, meaningful inventory and regeneration relationships, useful query opportunities, and bounded application scope. The original alternatives and research discussion remain in [pull request #1](https://github.com/jarcur1/csc4402-team-project/pull/1).

#### Enterprise and database need

A local nonprofit collects seeds from growers, stores identifiable harvest lots, tests germination, distributes seeds to members, and assigns growers to replenish varieties running low.

A variety is not the same as a physical seed lot. Two lots of the same tomato variety can have different growers, harvest dates, quantities, storage locations, and germination histories. Distributions and new harvests connect those records over time.

#### Proposed model

Core entities could include crops, varieties, growers, seed lots, storage locations, germination tests, members, distributions, distribution items, and grow-out assignments.

Interesting relationships and constraints:

- One variety has many seed lots; each lot has its own test history.
- A distribution can contain seeds from multiple lots.
- Distribution transactions must not reduce available stock below zero.
- Germinated seed counts must be between zero and the number tested.
- New harvests are new lots, not returns of the original seeds.

#### Five candidate queries

1. Which varieties have insufficient available stock?
2. Which lots have low germination according to their latest test?
3. Which varieties were distributed most during a selected season?
4. Which members received seeds from a particular lot?
5. Which grow-out assignments remain unfinished after their due date?

#### Application scope

One application with menus for lot intake/inventory, germination-test entry, member distribution, and grow-out coordination. Include create, update, and delete operations where appropriate, with constraints protecting referenced records.

**Exclude:** Genetics, weather feeds, mapping, online payments, and automated agricultural advice.

**Main risk:** Confusing varieties with physical lots, or tracking stock in multiple places without keeping it consistent. Use one quantity unit and one agreed stock-accounting approach.

#### Sources

- [Seed Savers Exchange: How to Organize a Community Seed Bank](https://shop.seedsavers.org/site/pdf/Start-Seed-Bank.pdf) — incoming/outgoing inventory, germination testing, and grow-out commitments.
- [Seed Savers Exchange: The Seed Regeneration Process](https://seedsavers.org/the-seed-regeneration-process/) — replenishment because of low inventory or poor germination.

These sources describe real operations; the proposed schema and application scope are our design choices. Germination guidance should not be treated as a universal legal or biological cutoff.

## Work distribution

One person owns each of the five assignment parts. These are primary responsibilities, not isolated projects; everyone contributes to the report and final integration.

| Owner | Assignment part | Primary deliverables |
| --- | --- | --- |
| **Project lead (`jarcur1`; you)** | **2. Relational schema and inventory integrity — hardest technical task** | Executable schema, relational-schema explanation, keys/checks/foreign keys, transaction-safe stock operations, and the shared database contract. |
| **Joseph** | **1. E-R diagram** | Editable diagram and report-ready export, entity/attribute definitions, primary keys, cardinalities, and participation constraints. |
| **Luke** | **3. Data generation** | Reproducible synthetic-data generator and a populated database with coherent inventory histories and meaningful query cases. |
| **Owen** | **4. Five test queries** | Exactly five executable queries, documented parameters, deterministic expected results, and instructions to execute them. |
| **Trey** | **5. Application interfaces** | One CLI application with four bounded workflow menus, input/update/delete support, validation messages, and interface illustrations for the report. |

Roles below describe ownership. The project's [SQLite contract](database/README.md) includes fresh-database setup, integration signatures, and verification commands.

### Project lead: Relational schema and inventory integrity

**Why this is the hardest task:** Every other implementation depends on the schema, and stock correctness spans multiple tables and operations. A distribution must not oversell a lot or leave partially recorded data if an operation fails.

- Translate Joseph's agreed E-R model into normalized relations.
- Own `database/schema.sql` and the shared database operations in `app/db.py`.
- Integrate using the [table and operation contract](database/README.md), aligned with the [E-R model](design/er-model.md).
- Define primary/foreign keys, uniqueness, required fields, valid states, and deletion rules.
- Use integer seed counts consistently. Agree on one authoritative stock-accounting approach; avoid independently maintained totals that can disagree.
- Make distribution header/items and their stock changes one atomic transaction. Reject insufficient stock without leaving partial records.
- Define how intake, distributions, corrections/deletions, germination-test consumption, and seeds issued for grow-outs affect inventory.
- Require a positive number of seeds tested and a sprouted count between zero and that number.
- Enable SQLite foreign-key enforcement for every application/generator connection and protect referenced history from accidental deletion.
- Publish table/column names, database initialization order, allowed states, and database-operation signatures for Luke, Owen, and Trey.
- Supply the relational-schema report section and narrowly scoped integrity checks, including rollback on insufficient stock.

**First handoff:** Work with Joseph to settle the model, then publish the initial schema and database-operation contract before dependent implementations integrate.

### Joseph: E-R diagram

- Own `design/er-diagram.drawio` and a readable exported diagram at `design/er-diagram.pdf`.
- Distinguish crops, varieties, physical seed lots, and newly harvested replacement lots.
- Model distribution items, germination-test history, member relationships, storage, and grow-out assignments.
- Mark keys, relationship cardinalities, optional/mandatory participation, and relevant attributes.
- Include the attributes needed by Owen's five questions, such as stock targets, transaction/test dates, and grow-out due dates.
- Review the model with the project lead so the diagram and actual schema agree.
- Supply the E-R report section and a concise entity/attribute dictionary.

**First handoff:** Propose the entities and relationships for a team review. Do not wait for a polished diagram before resolving model questions.

### Luke: Synthetic data generation

- Own `scripts/generate_data.py` and the generated submission database at `database/seedbank.db`.
- Generate synthetic members/growers, varieties, lots, tests, distributions, and grow-out assignments without outside services or real personal data.
- Use a fixed random seed and a documented reference date so reruns reproduce Owen's expected query results.
- Include multiple lots per variety, multiple tests per lot, low-stock and zero-stock cases, differing demand, and both completed and overdue grow-outs.
- Keep dates, quantities, foreign keys, and consumption histories consistent; do not simply generate unrelated random rows.
- Use the agreed schema and stock operations rather than bypassing integrity rules.
- Document how to generate a fresh database without silently overwriting an existing working database.
- Supply the data-generation explanation, generation command, and dataset summary for the submission.

**First handoff:** Agree on representative scenarios with Owen while Joseph and the project lead finalize the model.

### Owen: Five test queries and expected results

- Own `queries/test_queries.sql` and `queries/expected_results.md`.
- Implement the five seed-bank questions listed above; agree on parameter values, low-stock/low-germination definitions, and the reference date.
- Make "latest germination test" deterministic if a lot has more than one test on the same date.
- Ensure joins do not double-count stock or distributions, and include varieties with no available stock where appropriate.
- Use Luke's reproducible dataset and show actual expected rows, not just descriptions of what a query should return.
- Provide an exact execution command and a stable output ordering for each query.
- Supply the report's five query explanations and sample outcomes.

**First handoff:** Send required fields and representative scenarios to Joseph, the project lead, and Luke before the schema is finalized.

### Trey: Application interfaces

- Own `app/cli.py` and the application-interface report section.
- Build one local CLI application, not four separate applications or a web frontend.
- Provide four workflow menus: lot intake/inventory, germination-test entry, member distribution, and grow-out coordination.
- Include the member/grower/variety record maintenance needed to use these workflows; keep it within the same application.
- Support appropriate create, update, and delete operations. Show understandable errors for invalid input or protected referenced records.
- Call the project lead's shared database operations; do not duplicate stock-accounting or transaction logic in the CLI.
- Capture representative menu interactions for the report and document how to launch the application.

**First handoff:** Sketch the four menus and send the required database-operation signatures to the project lead. UI design can start before the schema is implemented.

## Implementation baseline

Use **Python, SQLite, and a CLI** as the working baseline. This fits the assignment and requires no hosting, external accounts, payment systems, or live integrations.

Use synthetic data only. Keep genetics, weather feeds, mapping, online payments, and automated agricultural advice outside the project.

## Handoffs and shared integration

1. **Agree on the model:** Joseph and the project lead lead the review; Luke, Owen, and Trey bring dataset, query, and workflow requirements.
2. **Publish the contract:** The project lead publishes the schema and shared database-operation interface. Review stock units, date conventions, allowed states, deletion behavior, and transaction boundaries together.
3. **Implement in parallel:** Luke builds the generator, Owen implements the five queries, and Trey builds the CLI against the agreed contract. Joseph keeps the diagram synchronized.
4. **Prove the complete workflow:** Starting from a fresh database, generate data, execute all five queries, and exercise intake, test entry, distribution, and grow-out coordination. Check failed distributions leave stock and records unchanged.
5. **Assemble the submission together:** Each owner contributes their report section, execution instructions, and participation details. Keep the full report within eight pages and package all required database, application, generator, and test files.

Integration and packaging are shared responsibilities, not a sixth person's job. Discuss schema changes with every affected owner before integrating them.

Use feature branches and pull requests. Have another teammate review before merging; do not push directly to `main`.



Relationship	Cardinality	Draft explanation
Crop → Variety	One-to-many	A crop has multiple varieties; each variety belongs to one crop.
Variety → Seed Lot	One-to-many	A variety can have several physical lots from different harvests. Each lot contains one variety.
Grower → Seed Lot	One-to-many	A grower can contribute multiple lots; each lot records its contributing grower.
Storage Location → Seed Lot	One-to-many	A location can store multiple lots; each lot has one current location.
Seed Lot → Germination Test	One-to-many	A lot can have multiple tests over time. Each test belongs to exactly one lot.
Member → Distribution	One-to-many	A member can receive multiple distributions; each distribution has one recipient.
Distribution → Distribution Item	One-to-many	A distribution contains one or more items. Each item records a lot and the quantity issued.
Seed Lot → Distribution Item	One-to-many	A lot can supply multiple distribution items. Distribution items resolve the many-to-many relationship between distributions and lots.
Variety → Grow-out Assignment	One-to-many	Each assignment requests regeneration of one variety. A variety can have multiple assignments.
Grower → Grow-out Assignment	One-to-many	Each assignment belongs to one grower; a grower can receive multiple assignments.
Seed Lot → Grow-out Assignment	One-to-many, proposed	An assignment can reference one source lot used for planting. A source lot can supply multiple assignments.
Grow-out Assignment → New Seed Lot	One-to-many, proposed	An assignment can produce zero or more new harvest lots. Each resulting lot optionally references its originating assignment.


Suggested attributes for the four main records:
Record	Draft attributes
Seed Lot	Lot ID, variety, contributing grower, harvest date, storage location, quantity received, originating grow-out assignment if applicable
Distribution	Distribution ID, member, distribution date; items contain lot and quantity issued
Germination Test	Test ID, lot, test date, number tested, number germinated
Grow-out Assignment	Assignment ID, variety, assigned grower, optional source lot, quantity issued, assigned date, due date, status


Points to settle before finalizing the schema:
- Can one grow-out use multiple source lots? This draft assumes at most one.
- Can one grow-out produce multiple harvest lots? This draft allows it.
- Track germination-test consumption and grow-out seed issuance consistently with distributions, using integer seed counts and one agreed inventory approach.
- Treat harvested seeds as new lots, preserving their connection to the grow-out.
This is a proposed relationship draft for team review. No final schema, database file, or repository changes were created.
