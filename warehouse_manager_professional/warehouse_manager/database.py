"""
Database layer for Warehouse Manager.

Provides a wrapper around sqlite3 with automatic migrations and API
methods for customers, materials, serials and assignments.

NOTE: This module must be import‑safe: it must not create any Tkinter
objects or cause side effects when imported. All initialisation
happens lazily in the Database class.
"""

from __future__ import annotations

import os
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any


LOGGER = logging.getLogger(__name__)


class Database:
    """SQLite backed data layer for warehouse management.

    Parameters
    ----------
    path : str
        Path to the SQLite database file. If the file does not exist,
        it will be created and the schema initialised.

    The database uses Write‑Ahead Logging (WAL) for better concurrency
    and performance. Migrations are stored in the `schema_version`
    table. If new migrations are added, bump the version and add a
    corresponding migration function.
    """

    def __init__(self, path: str = "warehouse.db") -> None:
        self.path = path
        # Ensure directory exists
        db_path = Path(path)
        if db_path.parent and not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
        # Connect to the database
        self.conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema management
    def _ensure_schema(self) -> None:
        """Ensure the database schema is up to date."""
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            );
            """
        )
        cur.execute("SELECT COUNT(*) as count FROM schema_version;")
        count = cur.fetchone()[0]
        if count == 0:
            # fresh database
            cur.execute("INSERT INTO schema_version (version) VALUES (0);")
            self.conn.commit()
        version = self.get_schema_version()
        # List of migration functions in order. New migrations must be appended
        migrations = [self._migration_1, self._migration_2, self._migration_3]
        # Apply migrations sequentially
        for target_version, migration in enumerate(migrations, start=1):
            if version < target_version:
                LOGGER.info("Applying migration %s", target_version)
                migration()
                cur.execute("UPDATE schema_version SET version=?", (target_version,))
                self.conn.commit()

        # After applying all migrations, ensure a default admin user exists
        # without interfering with unit tests or multiple instances.
        try:
            self._ensure_default_admin_user()
        except Exception as exc:
            LOGGER.error("Failed to ensure default admin user: %s", exc)

    def get_schema_version(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT version FROM schema_version;")
        return int(cur.fetchone()[0])

    def _migration_1(self) -> None:
        """Initial schema creation."""
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                pin4 TEXT,
                last_modified REAL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                model TEXT NOT NULL,
                producer TEXT,
                description TEXT,
                image_path TEXT,
                retail_price REAL,
                is_used INTEGER DEFAULT 0,
                warranty_months INTEGER,
                category TEXT,
                auto_category TEXT,
                auto_confidence REAL DEFAULT 0.0,
                model_family TEXT,
                last_modified REAL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS serial_numbers (
                serial TEXT PRIMARY KEY,
                material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                production_date DATE,
                acquisition_date DATE,
                warranty_expiration DATE,
                assigned_to TEXT REFERENCES customers(id) ON DELETE SET NULL,
                last_modified REAL DEFAULT (strftime('%s','now')),
                extra_json TEXT,
                retail_price REAL
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                serial TEXT NOT NULL REFERENCES serial_numbers(serial) ON DELETE CASCADE,
                assigned_date DATE NOT NULL,
                material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                material_name TEXT NOT NULL,
                material_model TEXT NOT NULL,
                warranty_expiration DATE,
                last_modified REAL DEFAULT (strftime('%s','now')),
                deleted INTEGER DEFAULT 0,
                extra_json TEXT
            );

            CREATE TABLE IF NOT EXISTS category_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
                category TEXT
            );

            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            );
            """
        )
        # Create indices
        cur.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
            CREATE INDEX IF NOT EXISTS idx_materials_name ON materials(name);
            CREATE INDEX IF NOT EXISTS idx_materials_model ON materials(model);
            CREATE INDEX IF NOT EXISTS idx_materials_auto_category ON materials(auto_category);
            CREATE INDEX IF NOT EXISTS idx_serial_numbers_material_id ON serial_numbers(material_id);
            CREATE INDEX IF NOT EXISTS idx_assignments_customer_id ON assignments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_assignments_serial ON assignments(serial);
            """
        )

    def _migration_2(self) -> None:
        """Placeholder for future migrations."""
        # No schema changes for now.
        pass

    def _migration_3(self) -> None:
        """Add users table for authentication and roles."""
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL
            );
            """
        )
        # Optional: create index on role for quick lookup
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);"
        )
        # After creating table, ensure there is at least one admin user
        # We defer adding a default admin user until after migrations run
        

    # ------------------------------------------------------------------
    # Customer operations
    def add_customer(self, customer_id: str, name: str, phone: Optional[str] = None,
                     email: Optional[str] = None, pin4: Optional[str] = None) -> None:
        """Add a new customer to the database.

        Raises sqlite3.IntegrityError if customer_id already exists.
        """
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO customers (id, name, phone, email, pin4, last_modified)"
            " VALUES (?, ?, ?, ?, ?, strftime('%s','now'));",
            (customer_id, name, phone, email, pin4)
        )
        self.conn.commit()

    def update_customer(self, customer_id: str, **fields: Any) -> None:
        """Update fields of a customer.

        fields: dict of column names to new values. Only allowed columns
        (name, phone, email, pin4) are updated.
        """
        allowed = {"name", "phone", "email", "pin4"}
        keys = [k for k in fields.keys() if k in allowed]
        if not keys:
            return
        assignments = ", ".join(f"{k}=?" for k in keys)
        params = [fields[k] for k in keys]
        params.append(customer_id)
        sql = f"UPDATE customers SET {assignments}, last_modified=strftime('%s','now') WHERE id=?"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()

    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id=?", (customer_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def search_customers(self, query: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        like = f"%{query.lower()}%"
        cur.execute(
            "SELECT * FROM customers WHERE lower(name) LIKE ? OR lower(id) LIKE ? ORDER BY name ASC",
            (like, like)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_customer_history(self, customer_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT a.*, s.production_date, s.acquisition_date
            FROM assignments AS a
            LEFT JOIN serial_numbers AS s ON s.serial = a.serial
            WHERE a.customer_id = ?
            ORDER BY a.assigned_date DESC, a.id DESC
            """,
            (customer_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Materials & Serials
    def get_all_categories(self) -> List[str]:
        """Return distinct categories from materials table (including auto categories) that have at least one item."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT category FROM (
                SELECT category FROM materials WHERE category IS NOT NULL
                UNION ALL
                SELECT auto_category FROM materials WHERE auto_category IS NOT NULL
            ) WHERE category IS NOT NULL GROUP BY category HAVING COUNT(*) > 0
            ORDER BY category
            """
        )
        rows = cur.fetchall()
        return [row[0] for row in rows]

    def get_dynamic_categories(self, min_count: int = 3) -> List[str]:
        """Return auto categories that appear at least min_count times."""
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT auto_category FROM materials
            WHERE auto_category IS NOT NULL
            GROUP BY auto_category
            HAVING COUNT(*) >= ?
            ORDER BY auto_category;
            """,
            (min_count,)
        )
        return [row[0] for row in cur.fetchall()]

    def get_all_materials(self, is_used: int = 0, name_query: Optional[str] = None,
                          category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return all materials filtered by whether they are used, name query and category.
        """
        cur = self.conn.cursor()
        clauses = ["is_used = ?"]
        params: List[Any] = [is_used]
        if name_query:
            clauses.append("(lower(name) LIKE ? OR lower(model) LIKE ?)")
            like = f"%{name_query.lower()}%"
            params.extend([like, like])
        if category:
            # match both manual and auto category
            clauses.append("(category = ? OR auto_category = ?)")
            params.extend([category, category])
        where = " AND ".join(clauses)
        sql = f"SELECT *, (SELECT COUNT(*) FROM serial_numbers WHERE material_id = materials.id AND assigned_to IS NULL) AS available_serials, (SELECT COUNT(*) FROM serial_numbers WHERE material_id = materials.id) AS total_serials FROM materials WHERE {where} ORDER BY name, model"
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def add_material(self, name: str, model: str, producer: Optional[str] = None,
                     description: Optional[str] = None, image_path: Optional[str] = None,
                     retail_price: Optional[float] = None, is_used: int = 0,
                     warranty_months: Optional[int] = None) -> int:
        """Add a new material. Returns the inserted material id."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO materials (name, model, producer, description, image_path, retail_price, is_used, warranty_months, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, strftime('%s','now'))
            """,
            (name, model, producer, description, image_path, retail_price, is_used, warranty_months)
        )
        material_id = cur.lastrowid
        self.conn.commit()
        return material_id

    def set_material_fields(self, material_id: int, **fields: Any) -> None:
        """Update fields on a material. Accepts any column, but ensures last_modified updated."""
        if not fields:
            return
        assignments = ", ".join(f"{k}=?" for k in fields.keys())
        params = list(fields.values())
        params.append(material_id)
        sql = f"UPDATE materials SET {assignments}, last_modified=strftime('%s','now') WHERE id=?"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()

    def get_serials_by_material(self, material_id: int, include_assigned: bool = False) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if include_assigned:
            cur.execute(
                "SELECT * FROM serial_numbers WHERE material_id = ? ORDER BY production_date",
                (material_id,)
            )
        else:
            cur.execute(
                "SELECT * FROM serial_numbers WHERE material_id = ? AND assigned_to IS NULL ORDER BY production_date",
                (material_id,)
            )
        return [dict(row) for row in cur.fetchall()]

    def add_serials_to_material(self, material_id: int, serials: List[str],
                                production_date: Optional[str] = None,
                                acquisition_date: Optional[str] = None,
                                retail_price: Optional[float] = None) -> None:
        """Bulk insert serial numbers for a material.

        If a serial already exists, it will be skipped and logged. Fails atomically on constraint violation.
        """
        cur = self.conn.cursor()
        for serial in serials:
            try:
                cur.execute(
                    """
                    INSERT INTO serial_numbers (serial, material_id, production_date, acquisition_date, retail_price, last_modified)
                    VALUES (?, ?, ?, ?, ?, strftime('%s','now'))
                    """,
                    (serial, material_id, production_date, acquisition_date, retail_price)
                )
            except sqlite3.IntegrityError as exc:
                LOGGER.warning("Serial %s already exists; skipping: %s", serial, exc)
        self.conn.commit()

    def delete_serials(self, serials: List[str]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            f"DELETE FROM serial_numbers WHERE serial IN ({','.join('?' for _ in serials)})",
            serials
        )
        self.conn.commit()

    def resolve_serials_for_customer(self, serials: List[str]) -> Tuple[List[str], List[str]]:
        """
        Given a list of serial strings, return two lists: (valid, invalid).
        Valid serials are those that exist in database and are currently unassigned.
        """
        if not serials:
            return [], []
        cur = self.conn.cursor()
        placeholders = ",".join("?" for _ in serials)
        cur.execute(
            f"SELECT serial, assigned_to FROM serial_numbers WHERE serial IN ({placeholders})",
            serials
        )
        valid = []
        invalid = []
        seen = {row[0]: row[1] for row in cur.fetchall()}
        for s in serials:
            if s not in seen:
                invalid.append(s)
            else:
                if seen[s] is None:
                    valid.append(s)
                else:
                    invalid.append(s)
        return valid, invalid

    # ------------------------------------------------------------------
    # Assignment operations
    def assign_serial_to_customer(self, customer_id: str, serial: str) -> None:
        """Assign a serial to a customer. Creates an entry in assignments and marks serial assigned."""
        cur = self.conn.cursor()
        # Get material details
        cur.execute(
            "SELECT material_id, production_date, warranty_expiration FROM serial_numbers WHERE serial=? AND assigned_to IS NULL",
            (serial,)
        )
        res = cur.fetchone()
        if not res:
            raise ValueError(f"Serial {serial} not available or does not exist")
        material_id, prod_date, warranty_exp = res
        # fetch material info for assignment record
        cur.execute("SELECT name, model FROM materials WHERE id=?", (material_id,))
        material = cur.fetchone()
        if not material:
            raise ValueError(f"Material for serial {serial} not found")
        mat_name, mat_model = material
        cur.execute(
            """
            INSERT INTO assignments
            (customer_id, serial, assigned_date, material_id, material_name, material_model, warranty_expiration, last_modified)
            VALUES (?, ?, date('now'), ?, ?, ?, ?, strftime('%s','now'))
            """,
            (customer_id, serial, material_id, mat_name, mat_model, warranty_exp)
        )
        cur.execute(
            "UPDATE serial_numbers SET assigned_to=?, last_modified=strftime('%s','now') WHERE serial=?",
            (customer_id, serial)
        )
        self.conn.commit()

    def unassign_serial(self, serial: str, force: bool = False) -> None:
        """Unassign a serial from whatever customer it is assigned.

        If force is True, removes assignment record (marks deleted). If False, marks assignment deleted but keeps record.
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id FROM assignments WHERE serial=? AND deleted=0 ORDER BY assigned_date DESC LIMIT 1;
            """,
            (serial,)
        )
        row = cur.fetchone()
        if row:
            assignment_id = row[0]
            if force:
                cur.execute("DELETE FROM assignments WHERE id=?", (assignment_id,))
            else:
                cur.execute("UPDATE assignments SET deleted=1 WHERE id=?", (assignment_id,))
        cur.execute(
            "UPDATE serial_numbers SET assigned_to=NULL, last_modified=strftime('%s','now') WHERE serial=?",
            (serial,)
        )
        self.conn.commit()

    def transfer_serials_to_used(self, serials: List[str], from_customer: Optional[str] = None) -> None:
        """Move serials to used stock.

        Optionally unassign from customer first. Updates the materials.is_used flag for the referenced material if necessary.
        """
        cur = self.conn.cursor()
        for serial in serials:
            # Unassign if assigned and matches customer (if specified)
            cur.execute("SELECT assigned_to, material_id FROM serial_numbers WHERE serial=?", (serial,))
            row = cur.fetchone()
            if not row:
                continue
            assigned_to, material_id = row
            if assigned_to is not None and (from_customer is None or assigned_to == from_customer):
                self.unassign_serial(serial, force=False)
            # update material to used
            cur.execute("UPDATE materials SET is_used=1, last_modified=strftime('%s','now') WHERE id=?", (material_id,))
            # update serial
            cur.execute(
                "UPDATE serial_numbers SET last_modified=strftime('%s','now') WHERE serial=?",
                (serial,)
            )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Dynamic categorisation
    def autocategorize_material(self, material_id: int) -> Dict[str, Any]:
        """
        Run the categorizer on a single material and update its auto_category and confidence. Returns the info.
        """
        from .categorizer import guess_category
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM materials WHERE id=?", (material_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Material with id {material_id} does not exist")
        material = dict(row)
        cat, conf, family, _ev = guess_category(material, self)
        cur.execute(
            "UPDATE materials SET auto_category=?, auto_confidence=?, model_family=?, last_modified=strftime('%s','now') WHERE id=?",
            (cat, conf, family, material_id)
        )
        self.conn.commit()
        material['auto_category'] = cat
        material['auto_confidence'] = conf
        material['model_family'] = family
        return material

    def batch_autocategorize(self, only_uncategorized: bool = True) -> List[Dict[str, Any]]:
        """Run auto categorisation for all materials (optionally only those without manual category)."""
        cur = self.conn.cursor()
        if only_uncategorized:
            cur.execute("SELECT id FROM materials WHERE category IS NULL")
        else:
            cur.execute("SELECT id FROM materials")
        ids = [row[0] for row in cur.fetchall()]
        results = []
        for mid in ids:
            try:
                result = self.autocategorize_material(mid)
                results.append(result)
            except Exception as exc:
                LOGGER.error("Auto categorisation failed for material %s: %s", mid, exc)
        return results

    def set_material_category(self, material_id: int, category: Optional[str]) -> None:
        """Set the manual category for a material. Set to None to clear."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE materials SET category=?, last_modified=strftime('%s','now') WHERE id=?",
            (category, material_id)
        )
        self.conn.commit()

    def learn_category_alias(self, token: str, category: str) -> None:
        """Persist a token→category alias so future categorisations map to this category."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO category_aliases (token, category) VALUES (?, ?)",
            (token.lower(), category)
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Misc
    def get_last_change_time(self) -> float:
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(last_modified) FROM (SELECT last_modified FROM customers UNION ALL SELECT last_modified FROM materials UNION ALL SELECT last_modified FROM serial_numbers UNION ALL SELECT last_modified FROM assignments)")
        res = cur.fetchone()[0]
        return float(res) if res is not None else 0.0

    # ------------------------------------------------------------------
    # User management and authentication

    def _ensure_default_admin_user(self) -> None:
        """
        Create a default admin user if no users exist. This should only be called
        after migrations have been applied. The default credentials are
        username='admin' and password='admin', with role 'admin'. It is
        recommended that users change this password immediately.
        """
        cur = self.conn.cursor()
        # Check if users table exists; if not, nothing to do
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if not cur.fetchone():
            return
        cur.execute("SELECT COUNT(*) FROM users;")
        count = cur.fetchone()[0]
        if count == 0:
            LOGGER.info("No users found; creating default admin user")
            # Create a default super admin (admin1) user. Username 'admin'
            # with password 'admin' and highest privilege level 'admin1'.
            # It is recommended to change these credentials immediately.
            self.add_user('admin', 'admin', 'admin1')

    def _hash_password(self, password: str, salt: bytes) -> str:
        """
        Generate a password hash using PBKDF2-HMAC-SHA256. Returns the hex digest.
        """
        import hashlib
        # Use 100,000 iterations for reasonable security
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hashed.hex()

    def add_user(self, username: str, password: str, role: str) -> None:
        """
        Add a new user with the given role. Password is hashed with a random salt.
        Raises sqlite3.IntegrityError if the username already exists.
        """
        import os
        salt = os.urandom(16)
        password_hash = self._hash_password(password, salt)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt.hex(), role)
        )
        self.conn.commit()

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """
        Verify a username and password. Returns a dict with username and role
        if authentication succeeds, otherwise returns None.
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT username, password_hash, salt, role FROM users WHERE username=?", (username,)
        )
        row = cur.fetchone()
        if not row:
            return None
        stored_hash = row['password_hash']
        salt_bytes = bytes.fromhex(row['salt'])
        calc_hash = self._hash_password(password, salt_bytes)
        if calc_hash == stored_hash:
            return {'username': row['username'], 'role': row['role']}
        return None

    def get_user_role(self, username: str) -> Optional[str]:
        """
        Return the role for the given username, or None if user does not exist.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        return row['role'] if row else None

    # ------------------------------------------------------------------
    # User management helpers

    def list_users(self) -> List[Dict[str, Any]]:
        """
        Return a list of all users with their roles. Each entry is a dict with
        keys 'username' and 'role'.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT username, role FROM users ORDER BY username;")
        return [dict(row) for row in cur.fetchall()]

    def update_user_role(self, username: str, new_role: str) -> None:
        """
        Update the role for a given username. Does not perform any permission
        checks; callers must ensure they have appropriate privileges.
        """
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
        self.conn.commit()

    def delete_user(self, username: str) -> None:
        """
        Delete a user from the database. This does not cascade any records
        since other entities are not dependent on users. Deleting your own
        account is allowed but not recommended. Does nothing if user does not exist.
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM users WHERE username=?", (username,))
        self.conn.commit()
