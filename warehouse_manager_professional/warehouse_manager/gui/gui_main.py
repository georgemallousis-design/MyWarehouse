"""
Main GUI entry point for Warehouse Manager.

Creates the root window and the Notebook with Customers, Inventory and Used tabs.
"""

from __future__ import annotations

import logging
import threading
from tkinter import Tk, ttk
from typing import Optional

# Use absolute imports so that this script can be executed directly or via PyCharm
from warehouse_manager.database import Database
from warehouse_manager.gui.theme import apply_theme
from warehouse_manager.gui.customer_gui import CustomersTab
from warehouse_manager.gui.materials_gui import InventoryTab, UsedTab
from warehouse_manager.gui.login_gui import LoginWindow


LOGGER = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, db: Database, role: str, username: str, root: Optional["Tk"] = None, enable_used: bool = True) -> None:
        """
        Create the main application window.

        Parameters
        ----------
        db : Database
            The database instance.
        role : str
            The authenticated user's role. Determines available actions in the UI.
        username : str
            The authenticated user's username. Required for user management tab and
            to prevent editing or deleting the logged‑in user.
        root : tk.Tk, optional
            An existing Tk root to use for the application. If None, a new root
            will be created. Using a shared root allows the login dialog and
            main application to live in a single window without spawning a
            second blank window.
        enable_used : bool, optional
            Whether to show the 'Used' tab.
        """
        self.db = db
        self.role = role
        self.username = username
        self.enable_used = enable_used
        # If a root is provided, use it; otherwise create a new one. This allows
        # the login flow to reuse the same Tk instance so only one window
        # appears on screen.
        if root is not None:
            self.root = root
        else:
            self.root = Tk()
        # Apply theme and window properties. If the root was created
        # outside, these settings may already be applied, but applying
        # them again is harmless.
        apply_theme(self.root)
        self.root.title("Warehouse Manager")
        # Only set geometry if not already defined (e.g. from login)
        try:
            # If the root has no geometry set yet, set a default size
            if not self.root.winfo_geometry() or self.root.winfo_geometry() == '1x1+0+0':
                self.root.geometry("1000x600")
        except Exception:
            self.root.geometry("1000x600")
        # Build the main widgets after login
        self._create_widgets()
        # Run auto categorisation in the background
        threading.Thread(target=self._autocategorize_background, daemon=True).start()

    def _create_widgets(self) -> None:
        # Notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True)
        # Customers tab
        self.customers_tab = CustomersTab(notebook, self.db, self.role)
        notebook.add(self.customers_tab.frame, text="Customers")
        # Inventory tab
        self.inventory_tab = InventoryTab(notebook, self.db, self.role)
        notebook.add(self.inventory_tab.frame, text="Inventory")
        # Used tab (optional)
        if self.enable_used:
            self.used_tab = UsedTab(notebook, self.db, self.role)
            notebook.add(self.used_tab.frame, text="Used")

        # User management tab: only for admin roles
        try:
            from warehouse_manager.gui.user_management_gui import UsersTab  # type: ignore
            if self.role.startswith('admin'):
                self.users_tab = UsersTab(notebook, self.db, self.role, self.username)
                notebook.add(self.users_tab.frame, text="Users")
        except Exception as exc:
            LOGGER.error("Failed to load Users tab: %s", exc)

    def _autocategorize_background(self) -> None:
        """
        Run auto categorisation using a separate Database connection to avoid
        SQLite threading issues. This function runs in a background thread.
        """
        try:
            from warehouse_manager.database import Database as DBClass
            # Create a fresh connection for this thread
            db2 = DBClass(self.db.path)
            results = db2.batch_autocategorize()
            if results:
                LOGGER.info("Auto categorized %d materials", len(results))
                # Schedule refresh on the main thread
                self.root.after(0, self._refresh_tabs)
        except Exception as exc:
            LOGGER.error("Auto categorization thread error: %s", exc)

    def _refresh_tabs(self) -> None:
        if hasattr(self, 'inventory_tab'):
            self.inventory_tab.refresh()
        if hasattr(self, 'used_tab'):
            self.used_tab.refresh()

    def run(self) -> None:
        self.root.mainloop()


def main(db_path: Optional[str] = None) -> None:
    """Launch the Warehouse Manager GUI application with login.

    A single Tk root is created and used for both the login dialog and
    the main application. After successful authentication, the root
    window is reused to display the main UI, preventing multiple
    separate windows from appearing.
    """
    import argparse
    import tkinter as tk
    parser = argparse.ArgumentParser(description="Warehouse Manager GUI")
    parser.add_argument("--db", dest="db_path", default=db_path or "warehouse.db",
                        help="SQLite database path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    # Create or open database
    db = Database(args.db_path)
    # Create a single root window for the application
    root = tk.Tk()
    # Apply theme early so login dialog inherits styling
    apply_theme(root)
    # Hide the root until authentication succeeds
    root.withdraw()
    # Keep track of login result
    user_info: dict[str, str] = {}

    def on_login(username: str, role: str) -> None:
        """Callback invoked after successful login. Stores credentials and stops the event loop."""
        user_info['username'] = username
        user_info['role'] = role
        # Exit the login loop
        root.quit()

    # Show the modal login dialog as a child of the hidden root
    LoginWindow(root, db, on_login)
    # Start the event loop to process the login dialog
    root.mainloop()
    # If no role was set (user closed the dialog or login failed), exit
    if not user_info.get('role'):
        LOGGER.info("Login aborted or failed; exiting application.")
        try:
            root.destroy()
        except Exception:
            pass
        return
    # Authentication succeeded; retrieve credentials
    username = user_info.get('username') or ''
    role = user_info.get('role') or ''
    # Show the main window and reuse the same root
    root.deiconify()
    root.title("Warehouse Manager")
    # Instantiate the main application using the existing root
    app = MainWindow(db, role, username, root=root)
    # Run the main application loop (blocks until window closed)
    app.run()


if __name__ == '__main__':
    main()
