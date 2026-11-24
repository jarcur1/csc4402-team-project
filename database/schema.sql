PRAGMA foreign_keys = ON;
PRAGMA recursive_triggers = ON;
BEGIN IMMEDIATE;

CREATE TABLE crop (
    crop_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (trim(name) <> '')
) STRICT;

CREATE TABLE variety (
    variety_id INTEGER PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crop ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK (trim(name) <> ''),
    stock_target_seeds INTEGER NOT NULL CHECK (stock_target_seeds >= 0),
    UNIQUE (crop_id, name)
) STRICT;

CREATE TABLE grower (
    grower_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (trim(name) <> '')
) STRICT;

CREATE TABLE storage_location (
    location_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (trim(name) <> '')
) STRICT;

CREATE TABLE member (
    member_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (trim(name) <> '')
) STRICT;

CREATE TABLE seed_lot (
    lot_id INTEGER PRIMARY KEY,
    variety_id INTEGER NOT NULL REFERENCES variety ON DELETE RESTRICT,
    grower_id INTEGER NOT NULL REFERENCES grower ON DELETE RESTRICT,
    location_id INTEGER NOT NULL REFERENCES storage_location ON DELETE RESTRICT,
    origin_assignment_id INTEGER REFERENCES growout_assignment ON DELETE RESTRICT,
    harvested_on TEXT NOT NULL CHECK (length(harvested_on) = 10 AND date(harvested_on, '+0 days') IS harvested_on),
    received_on TEXT NOT NULL CHECK (length(received_on) = 10 AND date(received_on, '+0 days') IS received_on),
    seeds_received INTEGER NOT NULL CHECK (seeds_received > 0),
    lot_status TEXT NOT NULL CHECK (lot_status IN ('available', 'held', 'retired')),
    CHECK (received_on >= harvested_on),
    UNIQUE (lot_id, variety_id)
) STRICT;

CREATE TABLE germination_test (
    test_id INTEGER PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES seed_lot ON DELETE RESTRICT,
    tested_on TEXT NOT NULL CHECK (length(tested_on) = 10 AND date(tested_on, '+0 days') IS tested_on),
    seeds_tested INTEGER NOT NULL CHECK (seeds_tested > 0),
    seeds_germinated INTEGER NOT NULL CHECK (seeds_germinated BETWEEN 0 AND seeds_tested),
    sample_from_stock INTEGER NOT NULL CHECK (sample_from_stock IN (0, 1))
) STRICT;

CREATE TABLE distribution (
    distribution_id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES member ON DELETE RESTRICT,
    distributed_on TEXT NOT NULL CHECK (length(distributed_on) = 10 AND date(distributed_on, '+0 days') IS distributed_on)
) STRICT;

CREATE TABLE distribution_item (
    distribution_id INTEGER NOT NULL REFERENCES distribution ON DELETE RESTRICT,
    lot_id INTEGER NOT NULL REFERENCES seed_lot ON DELETE RESTRICT,
    seeds_issued INTEGER NOT NULL CHECK (seeds_issued > 0),
    PRIMARY KEY (distribution_id, lot_id)
) STRICT;

CREATE TABLE growout_assignment (
    assignment_id INTEGER PRIMARY KEY,
    variety_id INTEGER NOT NULL REFERENCES variety ON DELETE RESTRICT,
    grower_id INTEGER NOT NULL REFERENCES grower ON DELETE RESTRICT,
    source_lot_id INTEGER,
    assigned_on TEXT NOT NULL CHECK (length(assigned_on) = 10 AND date(assigned_on, '+0 days') IS assigned_on),
    due_on TEXT NOT NULL CHECK (length(due_on) = 10 AND date(due_on, '+0 days') IS due_on),
    issued_on TEXT CHECK (issued_on IS NULL OR (length(issued_on) = 10 AND date(issued_on, '+0 days') IS issued_on)),
    seeds_issued INTEGER CHECK (seeds_issued > 0),
    status TEXT NOT NULL CHECK (status IN ('assigned', 'in_progress', 'completed', 'cancelled')),
    FOREIGN KEY (source_lot_id, variety_id) REFERENCES seed_lot (lot_id, variety_id) ON DELETE RESTRICT,
    CHECK (due_on >= assigned_on),
    CHECK ((issued_on IS NULL) = (seeds_issued IS NULL)),
    CHECK (issued_on IS NULL OR (source_lot_id IS NOT NULL AND issued_on >= assigned_on)),
    CHECK (status <> 'completed' OR issued_on IS NOT NULL),
    CHECK (status <> 'assigned' OR issued_on IS NULL)
) STRICT;

CREATE TABLE stock_adjustment (
    adjustment_id INTEGER PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES seed_lot ON DELETE RESTRICT,
    adjusted_on TEXT NOT NULL CHECK (length(adjusted_on) = 10 AND date(adjusted_on, '+0 days') IS adjusted_on),
    delta_seeds INTEGER NOT NULL CHECK (delta_seeds <> 0),
    reason TEXT NOT NULL CHECK (trim(reason) <> '')
) STRICT;

CREATE INDEX seed_lot_by_variety ON seed_lot (variety_id, lot_status);
CREATE INDEX germination_test_by_lot ON germination_test (lot_id, tested_on DESC, test_id DESC);
CREATE INDEX distribution_by_date ON distribution (distributed_on);
CREATE INDEX distribution_item_by_lot ON distribution_item (lot_id);
CREATE INDEX growout_by_source ON growout_assignment (source_lot_id);
CREATE INDEX stock_adjustment_by_lot ON stock_adjustment (lot_id);

-- Only posted inputs determine on-hand stock. Lot status affects availability, not the balance.
CREATE VIEW lot_stock AS
SELECT l.lot_id,
       l.variety_id,
       l.lot_status,
       l.seeds_received
       - COALESCE((SELECT SUM(i.seeds_issued) FROM distribution_item AS i WHERE i.lot_id = l.lot_id), 0)
       - COALESCE((SELECT SUM(t.seeds_tested) FROM germination_test AS t WHERE t.lot_id = l.lot_id AND t.sample_from_stock = 1), 0)
       - COALESCE((SELECT SUM(g.seeds_issued) FROM growout_assignment AS g WHERE g.source_lot_id = l.lot_id AND g.issued_on IS NOT NULL), 0)
       + COALESCE((SELECT SUM(a.delta_seeds) FROM stock_adjustment AS a WHERE a.lot_id = l.lot_id), 0)
       AS on_hand_seeds
FROM seed_lot AS l;

CREATE VIEW variety_stock AS
SELECT v.variety_id, v.stock_target_seeds,
       COALESCE(SUM(l.on_hand_seeds), 0) AS available_seeds
FROM variety AS v
LEFT JOIN lot_stock AS l ON l.variety_id = v.variety_id AND l.lot_status = 'available'
GROUP BY v.variety_id;

-- The intake identity is historical; only location and availability may change.
CREATE TRIGGER seed_lot_check_origin BEFORE INSERT ON seed_lot
WHEN NEW.origin_assignment_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM growout_assignment AS g
    WHERE g.assignment_id = NEW.origin_assignment_id AND g.variety_id = NEW.variety_id
      AND g.grower_id = NEW.grower_id AND g.issued_on <= NEW.harvested_on
)
BEGIN
    SELECT RAISE(ABORT, 'harvest lot must match an issued assignment and follow its issue date');
END;

CREATE TRIGGER seed_lot_keep_intake BEFORE UPDATE OF
    lot_id, variety_id, grower_id, origin_assignment_id, harvested_on, received_on, seeds_received ON seed_lot
BEGIN
    SELECT RAISE(ABORT, 'lot intake cannot be changed; record a stock adjustment');
END;

CREATE TRIGGER seed_lot_keep_history BEFORE DELETE ON seed_lot
BEGIN
    SELECT RAISE(ABORT, 'lot intake cannot be deleted; retire the lot');
END;

CREATE TRIGGER germination_test_post AFTER INSERT ON germination_test
BEGIN
    SELECT RAISE(ABORT, 'test date precedes lot intake')
    WHERE NEW.tested_on < (SELECT received_on FROM seed_lot WHERE lot_id = NEW.lot_id);
    SELECT RAISE(ABORT, 'insufficient lot stock for germination sample')
    WHERE NEW.sample_from_stock = 1 AND EXISTS (
        SELECT 1 FROM lot_stock WHERE lot_id = NEW.lot_id
          AND (on_hand_seeds < 0 OR typeof(on_hand_seeds) <> 'integer')
    );
END;

CREATE TRIGGER germination_test_protect_sample BEFORE UPDATE ON germination_test
WHEN NEW.sample_from_stock <> OLD.sample_from_stock OR
     (OLD.sample_from_stock = 1 AND (
        NEW.test_id IS NOT OLD.test_id OR NEW.lot_id IS NOT OLD.lot_id OR
        NEW.tested_on IS NOT OLD.tested_on OR NEW.seeds_tested IS NOT OLD.seeds_tested
     ))
BEGIN
    SELECT RAISE(ABORT, 'posted sample cannot be changed; record a stock adjustment');
END;

CREATE TRIGGER germination_test_check_date BEFORE UPDATE OF lot_id, tested_on ON germination_test
WHEN NEW.tested_on < (SELECT received_on FROM seed_lot WHERE lot_id = NEW.lot_id)
BEGIN
    SELECT RAISE(ABORT, 'test date precedes lot intake');
END;

CREATE TRIGGER germination_test_keep_sample BEFORE DELETE ON germination_test
WHEN OLD.sample_from_stock = 1
BEGIN
    SELECT RAISE(ABORT, 'posted sample cannot be deleted; record a stock adjustment');
END;

-- post_distribution creates a header and at least one line in a single savepoint.
CREATE TRIGGER distribution_item_post AFTER INSERT ON distribution_item
BEGIN
    SELECT RAISE(ABORT, 'distribution requires an available lot received by the distribution date')
    WHERE NOT EXISTS (
        SELECT 1 FROM seed_lot AS l JOIN distribution AS d ON d.distribution_id = NEW.distribution_id
        WHERE l.lot_id = NEW.lot_id AND l.lot_status = 'available' AND l.received_on <= d.distributed_on
    );
    SELECT RAISE(ABORT, 'insufficient lot stock for distribution')
    WHERE EXISTS (
        SELECT 1 FROM lot_stock WHERE lot_id = NEW.lot_id
          AND (on_hand_seeds < 0 OR typeof(on_hand_seeds) <> 'integer')
    );
END;

CREATE TRIGGER distribution_keep_header BEFORE UPDATE ON distribution
WHEN EXISTS (SELECT 1 FROM distribution_item WHERE distribution_id = OLD.distribution_id)
BEGIN
    SELECT RAISE(ABORT, 'posted distribution cannot be changed');
END;

CREATE TRIGGER distribution_item_keep_update BEFORE UPDATE ON distribution_item
BEGIN
    SELECT RAISE(ABORT, 'posted distribution item cannot be changed; record a stock adjustment');
END;

CREATE TRIGGER distribution_item_keep_delete BEFORE DELETE ON distribution_item
BEGIN
    SELECT RAISE(ABORT, 'posted distribution item cannot be deleted; record a stock adjustment');
END;

CREATE TRIGGER growout_plan_first BEFORE INSERT ON growout_assignment
WHEN NEW.status <> 'assigned' OR NEW.issued_on IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'create an assigned grow-out before posting an issue');
END;

CREATE TRIGGER growout_keep_history BEFORE UPDATE ON growout_assignment
WHEN OLD.status IN ('completed', 'cancelled') OR NEW.assignment_id IS NOT OLD.assignment_id OR
     (OLD.issued_on IS NOT NULL AND (
        NEW.variety_id IS NOT OLD.variety_id OR NEW.grower_id IS NOT OLD.grower_id OR
        NEW.source_lot_id IS NOT OLD.source_lot_id OR NEW.assigned_on IS NOT OLD.assigned_on OR
        NEW.issued_on IS NOT OLD.issued_on OR NEW.seeds_issued IS NOT OLD.seeds_issued
     ))
BEGIN
    SELECT RAISE(ABORT, 'closed assignment or posted issue cannot be changed');
END;

CREATE TRIGGER growout_post_issue AFTER UPDATE ON growout_assignment
WHEN OLD.issued_on IS NULL AND NEW.issued_on IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'posting a grow-out issue must move the assignment to in progress')
    WHERE NEW.status <> 'in_progress';
    SELECT RAISE(ABORT, 'grow-out issuance requires an available source lot received by the issue date')
    WHERE NOT EXISTS (
        SELECT 1 FROM seed_lot WHERE lot_id = NEW.source_lot_id AND variety_id = NEW.variety_id
          AND lot_status = 'available' AND received_on <= NEW.issued_on
    );
    SELECT RAISE(ABORT, 'insufficient lot stock for grow-out issue')
    WHERE EXISTS (
        SELECT 1 FROM lot_stock WHERE lot_id = NEW.source_lot_id
          AND (on_hand_seeds < 0 OR typeof(on_hand_seeds) <> 'integer')
    );
END;

CREATE TRIGGER growout_keep_delete BEFORE DELETE ON growout_assignment
WHEN OLD.issued_on IS NOT NULL OR OLD.status IN ('completed', 'cancelled')
BEGIN
    SELECT RAISE(ABORT, 'posted or closed grow-out cannot be deleted');
END;

CREATE TRIGGER stock_adjustment_post AFTER INSERT ON stock_adjustment
BEGIN
    SELECT RAISE(ABORT, 'adjustment date precedes lot intake')
    WHERE NEW.adjusted_on < (SELECT received_on FROM seed_lot WHERE lot_id = NEW.lot_id);
    SELECT RAISE(ABORT, 'stock adjustment would make lot balance negative or exceed integer range')
    WHERE EXISTS (
        SELECT 1 FROM lot_stock WHERE lot_id = NEW.lot_id
          AND (on_hand_seeds < 0 OR typeof(on_hand_seeds) <> 'integer')
    );
END;

CREATE TRIGGER stock_adjustment_keep_update BEFORE UPDATE ON stock_adjustment
BEGIN
    SELECT RAISE(ABORT, 'stock adjustment cannot be changed; post a new adjustment');
END;

CREATE TRIGGER stock_adjustment_keep_delete BEFORE DELETE ON stock_adjustment
BEGIN
    SELECT RAISE(ABORT, 'stock adjustment cannot be deleted; post a new adjustment');
END;

COMMIT;
