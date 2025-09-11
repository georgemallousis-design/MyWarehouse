"""
Login dialog for Warehouse Manager.

This module defines a simple login window that prompts the user for a
username and password. It verifies the credentials using the Database
authenticate_user method. If authentication succeeds, a callback is
invoked with the username and role. If authentication fails, an error
is shown and the user can try again.

The login dialog is designed to be import‑safe and does not create
Tkinter root instances when imported. It requires an existing Tk
root or toplevel to be passed in.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable

from warehouse_manager.database import Database
from warehouse_manager.gui.theme import styled_button


class LoginWindow:
    """A modal login dialog that prompts for username and password."""

    def __init__(self, parent: tk.Widget, db: Database,
                 on_success: Callable[[str, str], None]) -> None:
        """
        Create a new LoginWindow.

        Parameters
        ----------
        parent : tk.Widget
            The parent widget (root or toplevel) on which this dialog
            will be centered.
        db : Database
            The database instance used to authenticate users.
        on_success : Callable[[str, str], None]
            A callback invoked with (username, role) upon successful
            login.
        """
        self.db = db
        self.on_success = on_success
        # Create a top‑level window to host the login form
        self.window = tk.Toplevel(parent)
        self.window.title("Login")
        # Make modal: grab_set prevents interaction with parent until closed
        self.window.grab_set()
        # Prevent resizing for a simple fixed dialog
        self.window.resizable(False, False)
        # Center the dialog over the parent
        self._center_on_parent(parent)
        # Build the form
        self._create_widgets()

    def _center_on_parent(self, parent: tk.Widget) -> None:
        """Center this window on its parent widget."""
        self.window.update_idletasks()
        parent.update_idletasks()
        # Compute positions
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        win_w = self.window.winfo_width()
        win_h = self.window.winfo_height()
        if win_w == 1 and win_h == 1:  # default size; wait for geometry manager
            win_w = 300
            win_h = 160
        x = parent_x + (parent_w // 2) - (win_w // 2)
        y = parent_y + (parent_h // 2) - (win_h // 2)
        self.window.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def _create_widgets(self) -> None:
        """Construct the login form widgets."""
        frame = ttk.Frame(self.window, padding=(20, 20))
        frame.pack(fill='both', expand=True)
        # Username
        ttk.Label(frame, text="Username:").grid(row=0, column=0, sticky='w')
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(frame, textvariable=self.username_var)
        username_entry.grid(row=0, column=1, pady=5, sticky='ew')
        username_entry.focus_set()
        # Password
        ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky='w')
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=self.password_var, show='*')
        password_entry.grid(row=1, column=1, pady=5, sticky='ew')
        # Bind Enter key to login
        password_entry.bind('<Return>', lambda e: self._do_login())
        # Login button
        login_btn = styled_button(frame, text="Login", command=self._do_login)
        login_btn.grid(row=2, column=0, columnspan=2, pady=(10, 0))

        # Create account button (sign up). This allows new users to register
        # with a default role of 'viewer'. Only basic information is required.
        signup_btn = styled_button(frame, text="Create account", command=self._do_signup)
        signup_btn.grid(row=3, column=0, columnspan=2, pady=(5, 0))

        frame.columnconfigure(1, weight=1)

    def _do_login(self) -> None:
        """Attempt to authenticate the entered credentials."""
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            messagebox.showerror("Missing fields", "Please enter both username and password.", parent=self.window)
            return
        auth = self.db.authenticate_user(username, password)
        if auth is None:
            messagebox.showerror("Login failed", "Invalid username or password.", parent=self.window)
            # Clear password field for security
            self.password_var.set("")
            return
        # Success
        # Clear fields to avoid leaving sensitive data
        self.username_var.set("")
        self.password_var.set("")
        # Destroy the login window and callback
        self.window.destroy()
        self.on_success(auth['username'], auth['role'])

    def _do_signup(self) -> None:
        """Prompt the user to create a new account with a default 'viewer' role."""
        # Ask for a username. Keep prompting until a non-empty value is entered
        username = None
        while True:
            username = simpledialog.askstring("Create Account", "Enter a username:", parent=self.window)
            if username is None:
                return  # user cancelled
            username = username.strip()
            if not username:
                messagebox.showerror("Error", "Username cannot be empty.", parent=self.window)
                continue
            break
        # Check if the username already exists
        existing_users = {u['username'] for u in self.db.list_users()}
        if username in existing_users:
            messagebox.showerror("Error", f"Username '{username}' is already taken.", parent=self.window)
            return
        # Ask for password and confirmation
        password = simpledialog.askstring("Create Account", "Enter a password:", parent=self.window, show='*')
        if password is None:
            return
        confirm = simpledialog.askstring("Create Account", "Confirm password:", parent=self.window, show='*')
        if confirm is None:
            return
        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match.", parent=self.window)
            return
        # Create the user with the lowest role ('viewer') by default
        try:
            self.db.add_user(username, password, 'viewer')
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to create account: {exc}", parent=self.window)
            return
        messagebox.showinfo("Account created", "Account created successfully. You can now log in.", parent=self.window)