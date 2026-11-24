from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from app import db


class SeedBankDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = self.enterContext(closing(db.connect(":memory:")))
        db.initialize(self.conn)
        crop = db.add_crop(self.conn, "Bean")
        self.variety = db.add_variety(self.conn, crop_id=crop, name="Blue Lake", stock_target_seeds=15)
        self.other = db.add_variety(self.conn, crop_id=crop, name="Provider", stock_target_seeds=5)
        self.grower = db.add_grower(self.conn, "Test Grower")
        self.location = db.add_location(self.conn, "Shelf 1")
        self.member = db.add_member(self.conn, "Test Member")
        self.lot = self.receive_lot()

    def receive_lot(self, seeds=10, **overrides):
        intake = dict(variety_id=self.variety, grower_id=self.grower, location_id=self.location,
                      harvested_on="2026-09-01", received_on="2026-09-02", seeds_received=seeds)
        return db.receive_lot(self.conn, **(intake | overrides))

    def balance(self, lot_id):
        return self.conn.execute("SELECT on_hand_seeds FROM lot_stock WHERE lot_id = ?", (lot_id,)).fetchone()[0]

    def distribute(self, items):
        return db.post_distribution(self.conn, member_id=self.member, distributed_on="2026-09-10", items=items)

    def growout(self, **kwargs):
        return db.create_growout(self.conn, variety_id=self.variety, grower_id=self.grower,
                                 assigned_on="2026-09-10", due_on="2026-11-01", **kwargs)

    def test_invalid_second_distribution_line_rolls_back_header_and_first_line(self):
        second = self.receive_lot(2)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "insufficient lot stock for distribution"):
            self.distribute(iter([(self.lot, 4), (second, 3)]))
        self.assertEqual((self.balance(self.lot), self.balance(second)), (10, 2))
        self.assertEqual(self.conn.execute("SELECT * FROM distribution").fetchall(), [])
        self.assertEqual(self.conn.execute("SELECT * FROM distribution_item").fetchall(), [])

        distribution_id = self.distribute(iter([(self.lot, 4), (second, 2)]))
        saved = self.conn.execute("""
            SELECT d.member_id, i.lot_id, i.seeds_issued
            FROM distribution AS d JOIN distribution_item AS i USING (distribution_id)
            WHERE d.distribution_id = ? ORDER BY i.lot_id
            """, (distribution_id,)).fetchall()
        self.assertEqual([tuple(row) for row in saved], [(self.member, self.lot, 4), (self.member, second, 2)])
        self.assertEqual((self.balance(self.lot), self.balance(second)), (6, 0))

    def test_empty_invalid_and_duplicate_distributions_leave_outer_transaction_intact(self):
        self.conn.execute("BEGIN")
        retained_id = self.distribute([(self.lot, 1)])
        bad_inputs = [[], [(self.lot, 0)], [(self.lot, 1), (self.lot, 1)]]
        for items in bad_inputs:
            with self.subTest(items=items), self.assertRaises(sqlite3.IntegrityError):
                self.distribute(items)
        self.assertTrue(self.conn.in_transaction)
        self.conn.commit()
        self.assertEqual(self.balance(self.lot), 9)
        self.assertEqual([row[0] for row in self.conn.execute("SELECT distribution_id FROM distribution")], [retained_id])

    def test_held_and_retired_lots_cannot_be_distributed_or_count_as_available(self):
        held = self.receive_lot(50, lot_status="held")
        retired = self.receive_lot(40, lot_status="retired")
        for lot in (held, retired):
            with self.subTest(lot=lot), self.assertRaisesRegex(sqlite3.IntegrityError, "available lot"):
                self.distribute([(lot, 2)])
        self.assertEqual(self.balance(held), 50)
        rows = self.conn.execute("SELECT * FROM variety_stock ORDER BY variety_id")
        self.assertEqual([tuple(row) for row in rows], [(self.variety, 15, 10), (self.other, 5, 0)])
        db.update_lot_storage(self.conn, self.lot, location_id=self.location, lot_status="retired")
        self.assertEqual(self.conn.execute("SELECT available_seeds FROM variety_stock WHERE variety_id = ?",
                                           (self.variety,)).fetchone()[0], 0)
        self.assertEqual(self.balance(self.lot), 10)

    def test_test_samples_and_adjustments_share_the_distribution_balance(self):
        self.distribute([(self.lot, 5)])
        test_id = db.record_test(self.conn, lot_id=self.lot, tested_on="2026-09-11",
                                 seeds_tested=3, seeds_germinated=2, sample_from_stock=True)
        external = db.record_test(self.conn, lot_id=self.lot, tested_on="2026-09-11",
                                  seeds_tested=20, seeds_germinated=19, sample_from_stock=False)
        db.correct_test_result(self.conn, test_id, 1)
        self.assertEqual(self.conn.execute("SELECT seeds_germinated FROM germination_test WHERE test_id = ?",
                                           (test_id,)).fetchone()[0], 1)
        db.delete_nonstock_test(self.conn, external)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "posted sample"):
            db.delete_nonstock_test(self.conn, test_id)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "insufficient lot stock for germination sample"):
            db.record_test(self.conn, lot_id=self.lot, tested_on="2026-09-12",
                           seeds_tested=3, seeds_germinated=1, sample_from_stock=True)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "balance negative"):
            db.adjust_stock(self.conn, lot_id=self.lot, adjusted_on="2026-09-12", delta_seeds=-3, reason="Count")
        self.assertEqual(self.balance(self.lot), 2)
        db.adjust_stock(self.conn, lot_id=self.lot, adjusted_on="2026-09-12", delta_seeds=1, reason="Count")
        db.adjust_stock(self.conn, lot_id=self.lot, adjusted_on="2026-09-13", delta_seeds=-3, reason="Damage")
        self.assertEqual(self.balance(self.lot), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM germination_test").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM stock_adjustment").fetchone()[0], 2)

    def test_issue_and_replacement_harvest_preserve_lineage(self):
        wrong_lot = self.receive_lot(variety_id=self.other)
        held = self.receive_lot(50, lot_status="held")
        with self.assertRaises(sqlite3.IntegrityError):
            self.growout(source_lot_id=wrong_lot)
        assignment = self.growout()
        db.revise_growout(self.conn, assignment, due_on="2026-11-02", source_lot_id=self.lot)
        with self.assertRaises(sqlite3.IntegrityError):
            self.receive_lot(origin_assignment_id=assignment, harvested_on="2026-10-03", received_on="2026-10-04")
        for source, count in ((wrong_lot, 1), (held, 1), (self.lot, 11)):
            with self.subTest(source=source, count=count), self.assertRaises(sqlite3.IntegrityError):
                db.issue_growout(self.conn, assignment, source_lot_id=source, issued_on="2026-09-11", seeds_issued=count)
        status = self.conn.execute("SELECT status, issued_on FROM growout_assignment WHERE assignment_id = ?",
                                   (assignment,)).fetchone()
        self.assertEqual(tuple(status), ("assigned", None))
        self.assertEqual(self.balance(self.lot), 10)
        db.issue_growout(self.conn, assignment, source_lot_id=self.lot, issued_on="2026-09-11", seeds_issued=4)
        self.assertEqual(self.balance(self.lot), 6)
        with self.assertRaises(sqlite3.IntegrityError):
            db.issue_growout(self.conn, assignment, source_lot_id=self.lot, issued_on="2026-09-11", seeds_issued=4)
        harvest = dict(origin_assignment_id=assignment, harvested_on="2026-10-01", received_on="2026-10-03")
        with self.assertRaises(sqlite3.IntegrityError):
            self.receive_lot(variety_id=self.other, **harvest)
        new_lots = [self.receive_lot(15, **harvest), self.receive_lot(20, **harvest)]
        db.set_growout_status(self.conn, assignment, "completed")
        self.assertEqual([self.balance(lot) for lot in [self.lot, *new_lots]], [6, 15, 20])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM seed_lot WHERE origin_assignment_id = ?",
                                           (assignment,)).fetchone()[0], 2)
        with self.assertRaises(sqlite3.IntegrityError):
            db.delete_growout(self.conn, assignment)

    def test_cancellation_of_issued_assignment_does_not_return_seeds(self):
        draft = self.growout()
        db.delete_growout(self.conn, draft)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM growout_assignment WHERE assignment_id = ?", (draft,)).fetchone())
        assignment = self.growout()
        db.issue_growout(self.conn, assignment, source_lot_id=self.lot, issued_on="2026-09-11", seeds_issued=3)
        db.set_growout_status(self.conn, assignment, "cancelled")
        self.assertEqual(self.balance(self.lot), 7)
        with self.assertRaises(sqlite3.IntegrityError):
            db.set_growout_status(self.conn, assignment, "assigned")

    def test_invalid_dates_references_and_counts_are_rejected(self):
        for override in ({"location_id": 9999}, {"seeds_received": 1.5}, {"seeds_received": 0},
                         {"harvested_on": "2026-02-30"}, {"received_on": "2026-08-01"}):
            with self.subTest(override=override), self.assertRaises(sqlite3.IntegrityError):
                self.receive_lot(**override)
        for tested, germinated in ((0, 0), (2, -1), (2, 3)):
            with self.subTest(tested=tested, germinated=germinated), self.assertRaises(sqlite3.IntegrityError):
                db.record_test(self.conn, lot_id=self.lot, tested_on="2026-09-10",
                               seeds_tested=tested, seeds_germinated=germinated, sample_from_stock=True)
        with self.assertRaises(sqlite3.IntegrityError):
            db.delete_catalog_entry(self.conn, "grower", self.grower)
        self.assertEqual(self.balance(self.lot), 10)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_posted_records_cannot_be_mutated_by_sql_or_replace(self):
        distribution_id = self.distribute([(self.lot, 2)])
        for sql, params in (
            ("UPDATE distribution SET distributed_on = '2026-10-02' WHERE distribution_id = ?", (distribution_id,)),
            ("DELETE FROM distribution WHERE distribution_id = ?", (distribution_id,)),
            ("UPDATE seed_lot SET seeds_received = 50 WHERE lot_id = ?", (self.lot,)),
            ("DELETE FROM seed_lot WHERE lot_id = ?", (self.lot,)),
            ("INSERT OR REPLACE INTO distribution_item VALUES (?, ?, 1)", (distribution_id, self.lot)),
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(sql, params)
        self.assertEqual(self.balance(self.lot), 8)

    def test_file_reopen_rejects_overselling_after_another_connection_commits(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "seedbank.db"
            with closing(db.connect(path)) as first, closing(db.connect(path)) as second:
                db.initialize(first)
                crop = db.add_crop(first, "Bean")
                variety = db.add_variety(first, crop_id=crop, name="Blue Lake", stock_target_seeds=4)
                grower = db.add_grower(first, "Test Grower")
                location = db.add_location(first, "Shelf 1")
                member = db.add_member(first, "Test Member")
                lot = db.receive_lot(first, variety_id=variety, grower_id=grower, location_id=location,
                                     harvested_on="2026-09-01", received_on="2026-09-02", seeds_received=4)
                db.post_distribution(first, member_id=member, distributed_on="2026-09-10", items=[(lot, 3)])
                with self.assertRaises(sqlite3.IntegrityError):
                    db.post_distribution(second, member_id=member, distributed_on="2026-09-10", items=[(lot, 2)])
                self.assertEqual(second.execute("SELECT on_hand_seeds FROM lot_stock").fetchone()[0], 1)
                self.assertEqual(second.execute("SELECT COUNT(*) FROM distribution").fetchone()[0], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    db.add_variety(second, crop_id=9999, name="Orphan", stock_target_seeds=0)


if __name__ == "__main__":
    unittest.main()
