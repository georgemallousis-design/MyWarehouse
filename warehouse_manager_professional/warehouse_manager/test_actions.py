"""
Acceptance actions for Warehouse Manager.

This module performs a sequence of operations against a test database
to verify that high level actions behave as expected. It is not a unit
test but can be executed manually.
"""

import tempfile
import os
from warehouse_manager.database import Database


def run_actions(dry_run: bool = True) -> None:
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "actions.db")
    db = Database(db_path)
    print("Creating test customer...")
    cid = "TEST-0001"
    db.add_customer(cid, "Test Customer", phone="123", email="test@example.com")
    print("Adding material with 3 serials...")
    mid = db.add_material("Switch", "TL-SG1005P", "TP-LINK", "PoE Switch", None, 50.0, is_used=0, warranty_months=12)
    db.add_serials_to_material(mid, ["SW1", "SW2", "SW3"], production_date="2025-01-01")
    print("Assigning SW1...")
    db.assign_serial_to_customer(cid, "SW1")
    print("Customer history after assignment:", db.get_customer_history(cid))
    print("Unassigning SW1...")
    db.unassign_serial("SW1")
    print("Moving SW2 to used...")
    db.transfer_serials_to_used(["SW2"])
    print("Serials by material:", db.get_serials_by_material(mid, include_assigned=True))
    print("Deleting SW3...")
    db.delete_serials(["SW3"])
    print("Adding bulk serials...")
    bulk = [f"B{i}" for i in range(10)]
    db.add_serials_to_material(mid, bulk)
    serials = db.get_serials_by_material(mid, include_assigned=True)
    print(f"Total serials after bulk add: {len(serials)}")
    print("Cleaning up test database...")
    os.remove(db_path)
    os.rmdir(tmp_dir)


if __name__ == '__main__':
    run_actions(dry_run=False)
