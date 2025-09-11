"""
Users management GUI for Warehouse Manager.

This module provides a tab that allows privileged administrators to
manage user accounts. Administrators can list existing users,
create new users with a specified role, edit the roles of existing
users, and delete users. Access to the user management tab is
controlled by the current user's role; only roles starting with
``admin`` (e.g. ``admin1``, ``admin2``, ``admin3``) may use this
functionality.

Hierarchical permissions are enforced as follows:

* ``admin1`` (level 4) may add, edit, or delete any user and assign
  any role, including creating other admin1s.
* ``admin2`` (level 3) may add, edit, or delete users whose role
  level is strictly lower than their own (admin3, operator, viewer).
  They cannot modify or delete admin1 users.
* ``admin3`` (level 2) may add, edit, or delete users with role
  levels strictly lower than their own (operator, viewer). They cannot
  modify or delete admin1 or admin2 users.
* ``operator`` and ``viewer`` (levels 1 and 0) never see this tab.

The tab uses a simple treeview to display existing accounts and
provides three buttons: ``Add User…``, ``Change Role…`` and
``Delete``. Each action performs appropriate permission checks
before altering the database.

The GUI is designed to be import‑safe and does not instantiate
Tkinter root windows upon import.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Dict, List

from warehouse_manager.database import Database
from warehouse_manager.gui.theme import styled_button, THEME

LOGGER = logging.getLogger(__name__)


# Define role hierarchy. Higher numbers represent higher privileges.
# Note: viewer and operator share the same low level. Admin levels
# increase with number, where admin1 is the highest.
ROLE_LEVELS: Dict[str, int] = {
    'viewer': 0,
    'operator': 1,
    'admin3': 2,
    'admin2': 3,
    'admin1': 4,
}

# List of all possible roles. Order is not important for logic.
ALL_ROLES: List[str] = ['viewer', 'operator', 'admin3', 'admin2', 'admin1']


class UsersTab:
    """A tab for viewing and managing application users."""

    def __init__(self, parent: ttk.Notebook, db: Database, current_role: str, current_username: str) -> None:
        self.db = db
        self.current_role = current_role
        self.current_username = current_username
        self.frame = ttk.Frame(parent)
        self._create_widgets()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction

    def _create_widgets(self) -> None:
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill='x')
        # Add user button
        self.add_btn = styled_button(toolbar, text="➕ Add User…", command=self._add_user)
        self.add_btn.pack(side='left', padx=5, pady=5)
        # Edit role button
        self.edit_btn = styled_button(toolbar, text="📝 Change Role…", command=self._change_role)
        self.edit_btn.pack(side='left', padx=5, pady=5)
        # Delete user button
        self.del_btn = styled_button(toolbar, text="🗑️ Delete", command=self._delete_user)
        self.del_btn.pack(side='left', padx=5, pady=5)
        # Treeview for users
        columns = ('username', 'role')
        self.tree = ttk.Treeview(self.frame, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('username', text='Username')
        self.tree.heading('role', text='Role')
        self.tree.column('username', anchor='w', width=200, stretch=True)
        self.tree.column('role', anchor='w', width=100, stretch=True)
        # Alternating row colours for readability
        self.tree.tag_configure('oddrow', background=THEME['ALT_BG'])
        self.tree.tag_configure('evenrow', background=THEME['CARD_BG'])
        self.tree.pack(fill='both', expand=True)
        # Bind double‑click to edit role
        self.tree.bind('<Double-1>', lambda e: self._change_role())

    # ------------------------------------------------------------------
    # Data refresh

    def refresh(self) -> None:
        """Reload the user list from the database."""
        # Clear existing entries
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Fetch all users and populate treeview
        try:
            users = self.db.list_users()
        except Exception as exc:
            LOGGER.error("Failed to list users: %s", exc)
            messagebox.showerror("Error", f"Failed to load users: {exc}", parent=self.frame)
            return
        for idx, user in enumerate(users):
            tag = 'oddrow' if idx % 2 else 'evenrow'
            self.tree.insert('', 'end', values=(user['username'], user['role']), tags=(tag,))

    # ------------------------------------------------------------------
    # Permission helpers

    def _role_level(self, role: str) -> int:
        """Return the numeric privilege level of a role."""
        return ROLE_LEVELS.get(role, -1)

    def _can_manage_role(self, target_role: str) -> bool:
        """Check whether the current user can manage (add/edit/delete) the given role."""
        return self._role_level(target_role) < self._role_level(self.current_role)

    def _allowed_new_roles(self) -> List[str]:
        """Return a list of roles that the current user is allowed to assign to new users."""
        my_level = self._role_level(self.current_role)
        allowed: List[str] = []
        for role in ALL_ROLES:
            # Admin1 can assign any role
            if self.current_role == 'admin1':
                allowed.append(role)
            else:
                # For other admins, only roles strictly below their level
                if self._role_level(role) < my_level:
                    allowed.append(role)
        return allowed

    # ------------------------------------------------------------------
    # Actions

    def _add_user(self) -> None:
        """Prompt for new user details and create a user if permitted."""
        # Determine which roles can be assigned by this admin
        options = self._allowed_new_roles()
        if not options:
            messagebox.showwarning("Access denied", "You do not have permission to add users.", parent=self.frame)
            return
        # Ask for username
        username = simpledialog.askstring("New User", "Enter username:", parent=self.frame)
        if not username:
            return
        # Check if username already exists
        existing_users = {u['username'] for u in self.db.list_users()}
        if username in existing_users:
            messagebox.showerror("Error", f"User '{username}' already exists.", parent=self.frame)
            return
        # Ask for password
        password = simpledialog.askstring("New User", "Enter password:", parent=self.frame, show='*')
        if not password:
            return
        confirm = simpledialog.askstring("New User", "Confirm password:", parent=self.frame, show='*')
        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match.", parent=self.frame)
            return
        # Ask for role from allowed options. Use a simple dropdown in a pop‑up window.
        role = self._choose_role("Select Role", options)
        if not role:
            return
        try:
            self.db.add_user(username, password, role)
            messagebox.showinfo("User created", f"User '{username}' created with role '{role}'.", parent=self.frame)
            self.refresh()
        except Exception as exc:
            LOGGER.error("Failed to add user: %s", exc)
            messagebox.showerror("Error", f"Failed to add user: {exc}", parent=self.frame)

    def _change_role(self) -> None:
        """Allow the administrator to change the role of a selected user."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select user", "Please select a user to change role.", parent=self.frame)
            return
        # Only allow editing one user at a time
        item_id = selected[0]
        username, current_role = self.tree.item(item_id, 'values')
        username = str(username)
        current_role = str(current_role)
        # Do not allow editing own role
        if username == self.current_username:
            messagebox.showwarning("Not allowed", "You cannot change your own role.", parent=self.frame)
            return
        # Check whether we can manage this user's role
        if not self._can_manage_role(current_role):
            messagebox.showwarning("Access denied", f"You do not have permission to change the role of '{username}'.", parent=self.frame)
            return
        # Determine roles we can assign
        my_level = self._role_level(self.current_role)
        allowed_roles = [r for r in ALL_ROLES if self._role_level(r) < my_level]
        # If current user is admin1, include admin1 as well
        if self.current_role == 'admin1':
            allowed_roles = ALL_ROLES.copy()
        # Remove current role from options if we don't want to present it twice
        # We still allow setting the same role (no change) though
        # Ask for new role
        new_role = self._choose_role(f"Change role for '{username}'", allowed_roles, preselect=current_role)
        if not new_role or new_role == current_role:
            return
        try:
            self.db.update_user_role(username, new_role)
            messagebox.showinfo("Role updated", f"Updated role for '{username}' to '{new_role}'.", parent=self.frame)
            self.refresh()
        except Exception as exc:
            LOGGER.error("Failed to update user role: %s", exc)
            messagebox.showerror("Error", f"Failed to update user role: {exc}", parent=self.frame)

    def _delete_user(self) -> None:
        """Delete the selected user if permitted."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select user", "Please select a user to delete.", parent=self.frame)
            return
        # Only operate on one user at a time for safety
        item_id = selected[0]
        username, role = self.tree.item(item_id, 'values')
        username = str(username)
        role = str(role)
        # Prevent self deletion
        if username == self.current_username:
            messagebox.showwarning("Not allowed", "You cannot delete your own account.", parent=self.frame)
            return
        # Check permission
        if not self._can_manage_role(role):
            messagebox.showwarning("Access denied", f"You do not have permission to delete '{username}'.", parent=self.frame)
            return
        # Confirm deletion
        if not messagebox.askyesno("Confirm delete", f"Are you sure you want to delete user '{username}'?", parent=self.frame):
            return
        try:
            self.db.delete_user(username)
            messagebox.showinfo("User deleted", f"User '{username}' deleted.", parent=self.frame)
            self.refresh()
        except Exception as exc:
            LOGGER.error("Failed to delete user: %s", exc)
            messagebox.showerror("Error", f"Failed to delete user: {exc}", parent=self.frame)

    # ------------------------------------------------------------------
    # Helper dialog to choose a role

    def _choose_role(self, title: str, roles: List[str], preselect: str | None = None) -> str | None:
        """Open a simple dialog to choose a role from a list. Returns the selected role or None."""
        # Create a transient toplevel window
        window = tk.Toplevel(self.frame)
        window.title(title)
        window.grab_set()
        # Keep it small and centered relative to the parent
        window.resizable(False, False)
        # Build simple form
        frm = ttk.Frame(window, padding=(20, 10))
        frm.pack(fill='both', expand=True)
        ttk.Label(frm, text="Role:").grid(row=0, column=0, sticky='w')
        role_var = tk.StringVar(value=preselect if preselect in roles else roles[0] if roles else '')
        combo = ttk.Combobox(frm, textvariable=role_var, values=roles, state='readonly')
        combo.grid(row=0, column=1, sticky='ew')
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        ok_btn = styled_button(btn_frame, text="OK", command=window.destroy)
        ok_btn.pack(side='left', padx=5)
        cancel = []

        def cancel_action() -> None:
            cancel.append(True)
            window.destroy()

        cancel_btn = styled_button(btn_frame, text="Cancel", command=cancel_action)
        cancel_btn.pack(side='left', padx=5)
        frm.columnconfigure(1, weight=1)
        # Center over parent
        window.update_idletasks()
        # centre the window relative to the frame
        parent_root = self.frame.winfo_toplevel()
        parent_root.update_idletasks()
        pw = parent_root.winfo_width()
        ph = parent_root.winfo_height()
        px = parent_root.winfo_rootx()
        py = parent_root.winfo_rooty()
        ww = window.winfo_width()
        wh = window.winfo_height()
        window.geometry(f"{ww}x{wh}+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")
        window.wait_window()
        if cancel:
            return None
        return role_var.get()