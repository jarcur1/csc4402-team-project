# CSC4402 Team Project

Five-person database project. This README is our shared shortlist: add alternatives, discuss tradeoffs, and record the team's choice before implementation.

**Decision status: Open — no enterprise has been selected.**

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

## Initial recommendations

Two research agents investigated different enterprise domains. After comparing scope, relational modeling opportunities, and fit to the five project parts, both endorsed this shortlist. The ordering is a recommendation, not a team decision.

### Option 1: Community Seed Bank & Regeneration Cooperative

**Best overall balance of originality, database depth, and manageable scope.**

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

### Option 2: Environmental Water-Testing Laboratory

**Best choice for a scientific or engineering enterprise.**

#### Enterprise and database need

A small laboratory accepts water-testing requests, tracks collected samples and custody handoffs, assigns requested tests, and records analytical results and reviews.

One client can have multiple sampling sites. Each sample can require several tests, and each requested test can have multiple analytical attempts. Custody history must remain associated with the correct physical sample.

#### Proposed model

Core entities could include clients, sites, service requests, samples, staff, custody transfers, test methods, test orders, and analytical runs/results.

Interesting relationships and constraints:

- Samples and test methods have a many-to-many relationship through test orders.
- Each test order can have multiple analytical runs, including rejected attempts and reruns.
- Each sample has a timestamped custody history.
- Results must reference an existing test order and identify the method and measurement unit.
- Review and completion states must distinguish an attempted test from an approved result.

#### Five candidate queries

1. Which requested tests have no approved result?
2. Which unfinished test orders are past their promised completion date?
3. Who handled a particular sample, and when?
4. Which repeat analytical runs produced materially different results under a defined comparison rule?
5. What are workload and average turnaround time by analyst and test method?

#### Application scope

One application with menus for request/sample intake, custody handoffs, and analytical result entry/review. Include create, update, and delete operations where appropriate, while preserving the integrity of linked sample records.

**Exclude:** Instrument integration, live sensors, billing, and declarations that water is legally compliant or safe.

**Main risk:** Expanding into regulatory compliance. Keep this an operational tracking system; do not implement simplified legal violation rules or universal safety thresholds.

#### Sources

- [EPA: Sample and Evidence Management](https://www.epa.gov/sites/default/files/2015-06/documents/Sample-and-Evidence-Management.pdf), particularly Sections 2.2 and 2.5 — sample identification, requested analyses, custody roles, and timestamped transfers.
- [USGS: National Field Manual, Processing of Water Samples](https://doi.org/10.3133/twri09A5) — background on processing samples and submitting them for analysis.

These sources ground the workflow, not a claim that the proposed student application satisfies laboratory accreditation or regulatory requirements.

### Option 3: Reusable Takeaway Container Pool

**Best choice for a straightforward business workflow with visible state changes.**

#### Enterprise and database need

A local company supplies reusable food containers to participating cafes. Customers can return containers at another partner location; containers are washed, inspected, and recirculated.

Containers move between businesses and customers. Returns, washing batches, inspections, and retirement records determine whether they can be issued again. The focus is the container lifecycle, not restaurant orders.

#### Proposed model

Core entities could include partner businesses, locations, container types, individual containers, borrowers, loans, returns, wash batches, batch items, and inspections.

Interesting relationships and constraints:

- Each container has a unique identity and can have many historical loans, but at most one active loan.
- A return location can differ from the issuing location.
- Wash batches contain multiple containers, and containers can pass through multiple batches over time.
- Returned containers cannot be reissued until the required cleaning/inspection workflow is complete.
- Retired containers cannot be checked out.

#### Five candidate queries

1. Which containers are overdue for return?
2. Which partner locations are below their clean-stock target?
3. Where was each container issued and returned?
4. Which returned containers have not passed the required cleaning/inspection workflow?
5. Which container types have the highest retirement rate after repeated use?

#### Application scope

One application with menus for issue/return, washing and inspection, and partner inventory management. Include create, update, and delete operations where appropriate, without orphaning lifecycle records.

**Exclude:** Payment processing, actual barcode hardware, delivery-route optimization, and restaurant ordering.

**Main risk:** Reducing the model to a basic checkout system. Keep cross-location returns, wash-batch membership, and inspections explicit.

#### Sources

- [reCIRCLE: Restaurant Program](https://www.recircle.ch/en/restaurant/) — a reusable packaging network, exchanges and returns, partner-business returns, replacements, and end-of-life recovery.

Individual-container IDs and wash-batch records are proposed project design choices, not claims about reCIRCLE's internal database.

## Five-person ownership plan

Assign one primary owner to each listed part. Ownership does not mean working in isolation.

| Owner | Part | Main responsibilities |
| --- | --- | --- |
| Person 1 — unassigned | E-R diagram | Lead entity/relationship definitions, keys, cardinalities, and the diagram. |
| Person 2 — unassigned | Relational schema | Translate the agreed model into SQL tables, foreign keys, checks, and other necessary constraints. |
| Person 3 — unassigned | Data generation | Produce a reproducible synthetic dataset with coherent histories and useful boundary cases. |
| Person 4 — unassigned | Five test queries | Define the five questions early; provide executable SQL and reproducible expected results. |
| Person 5 — unassigned | Application interfaces | Build one application with three or four role-based menus and appropriate input/update/delete operations. |

### Shared integration rules

- Agree on the enterprise workflows and E-R model together before implementing separate parts.
- The E-R and schema owners lead agreement on table names, keys, relationships, and allowed states.
- Stabilize the initial schema before integrating the generator, queries, and interfaces; communicate subsequent changes to every affected owner.
- Each person writes their report contribution and participation details.
- Share execution instructions and final integration checks; these are not a sixth person's job.
- Keep the interface scope bounded so the fifth owner is not responsible for building a large frontend.

**Suggested stack, not yet selected:** Python, SQLite, and a CLI. This fits the assignment without requiring hosting or a web framework.

## Add options and make a choice

### How to propose another enterprise

Add a new numbered option above the ownership plan, using the same structure:

1. Enterprise and why it needs a relational database.
2. Proposed entities and at least two interesting relationships or constraints.
3. Five useful query questions.
4. Three or four bounded interface workflows.
5. Explicit exclusions and the main implementation risk.
6. Links to sources for real operational details.

Use synthetic data for all options. External services and real customer records should not be prerequisites.

### How to compare options

Discuss these criteria before choosing:

- Can we explain the enterprise and its scope clearly within the report limit?
- Are the entities and relationships meaningful rather than invented to inflate the schema?
- Can we generate coherent data and demonstrate five useful queries?
- Can one person reasonably own the interface part?
- Can we run the complete submission locally without outside accounts or integrations?
- Does the group actually want to work on this domain?

Use pull-request comments for discussion and README edits for durable proposals. Work on a feature branch, open a pull request, and have another teammate review before merging.

### Decision record

**No team choice, vote, or owner assignment has been recorded yet.**

Once the group agrees, replace this statement with the selected enterprise, decision date, short rationale, agreed exclusions, chosen stack, and the five owners. Keep the other options for context.
