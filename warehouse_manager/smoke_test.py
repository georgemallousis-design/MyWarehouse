"""
Basic smoke test for the Warehouse Manager database layer.

This test module exercises core functionality such as adding customers,
materials, serials, assigning/unassigning, and moving to used stock.

Run this file directly to perform a quick sanity check. It does not
test the GUI.
"""

import tempfile
import os
from warehouse_manager.database import Database


def run_smoke_test() -> None:
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    db = Database(db_path)
    # Add customer
    db.add_customer("C001", "Alpha Corp", phone="123456789", email="alpha@example.com", pin4="1234")
    # Add material
    mid = db.add_material("Camera 4MP", "DS-2CD2343G2-I", "HIKVISION", "Dome camera", None, 100.0, is_used=0, warranty_months=24)
    # Add serials
    db.add_serials_to_material(mid, ["S001", "S002", "S003"], production_date="2024-01-01")
    # Assign one serial to customer
    db.assign_serial_to_customer("C001", "S001")
    # Unassign
    db.unassign_serial("S001")
    # Move one serial to used
    db.transfer_serials_to_used(["S002"])
    # Print summaries
    customers = db.search_customers("")
    materials = db.get_all_materials()
    serials = db.get_serials_by_material(mid, include_assigned=True)
    print(f"Customers: {customers}\nMaterials: {materials}\nSerials: {serials}")
    # Clean up
    try:
        os.remove(db_path)
        # Remove WAL/shm files if present
        for suffix in ("-wal", "-shm"):
            p = db_path + suffix
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(tmp_dir)
    except Exception:
        pass


if __name__ == '__main__':
    run_smoke_test()
