"""
Customers tab and related windows.

This module defines the UI components for managing customers and their
assignments in the Warehouse Manager application.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import List, Optional

# Use absolute imports so that this module can run standalone
from warehouse_manager.database import Database
from warehouse_manager.gui.theme import styled_button, make_thumbnail, THEME


LOGGER = logging.getLogger(__name__)


class CustomersTab:
    """A tab for viewing and managing customers."""
    def __init__(self, parent: ttk.Notebook, db: Database, role: str) -> None:
        self.db = db
        self.role = role
        self.frame = ttk.Frame(parent)
        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill='x')
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        search_entry.bind('<Return>', lambda e: self.refresh())
        self.add_btn = styled_button(toolbar, text="➕ Add Customer", command=self._add_customer_dialog)
        self.add_btn.pack(side='left', padx=5)
        refresh_btn = styled_button(toolbar, text="🔄 Refresh", command=self.refresh)
        refresh_btn.pack(side='left')
        # Treeview for customers
        # Show the 4‑digit PIN as the first column instead of a separate ID
        columns = ('pin', 'name', 'phone', 'email')
        self.tree = ttk.Treeview(self.frame, columns=columns, show='headings', selectmode='browse')
        # Configure alternating row tags for better readability
        self.tree.tag_configure('oddrow', background=THEME['ALT_BG'])
        self.tree.tag_configure('evenrow', background=THEME['CARD_BG'])
        for col in columns:
            # Capitalize and adjust the header; use upper case for pin
            header = col.upper() if col == 'pin' else col.capitalize()
            self.tree.heading(col, text=header)
            self.tree.column(col, anchor='w', stretch=True)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', self._on_row_double_click)

        # Disable add button for roles that are not any form of admin.
        # All admin levels (admin1, admin2, admin3) should be able to add customers.
        # Viewer and operator roles cannot add customers.
        if not self.role.startswith('admin'):
            self.add_btn.configure(state='disabled')

    def refresh(self) -> None:
        query = self.search_var.get().strip()
        if query:
            customers = self.db.search_customers(query)
        else:
            customers = self.db.search_customers('')  # list all
        # clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, cust in enumerate(customers):
            tag = 'oddrow' if idx % 2 else 'evenrow'
            self.tree.insert('', 'end', values=(cust['id'], cust['name'], cust.get('phone'), cust.get('email')), tags=(tag,))

    def _on_row_double_click(self, event) -> None:
        item_id = self.tree.selection()
        if not item_id:
            return
        values = self.tree.item(item_id[0], 'values')
        customer_id = values[0]
        CustomerProfileWindow(self.frame, self.db, customer_id, self.role)

    def _add_customer_dialog(self) -> None:
        # Ask for customer details. Use the 4‑digit PIN as the identifier.
        name = simpledialog.askstring("Customer Name", "Enter customer name:", parent=self.frame)
        if not name:
            return
        phone = simpledialog.askstring("Phone", "Enter phone (optional):", parent=self.frame)
        email = simpledialog.askstring("Email", "Enter email (optional):", parent=self.frame)
        # The PIN serves as the unique identifier for the customer.
        pin4 = simpledialog.askstring("PIN", "Enter 4‑digit PIN (required):", parent=self.frame)
        if not pin4:
            return
        try:
            # Use the PIN as both the customer ID and the stored PIN. This
            # satisfies the requirement that the 4‑digit code acts as the
            # identifier and retains it in the pin4 column for clarity.
            self.db.add_customer(pin4, name, phone, email, pin4)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to add customer: {exc}")


class CustomerProfileWindow:
    """Detailed window for editing customer info and managing assignments."""
    def __init__(self, parent: tk.Widget, db: Database, customer_id: str, role: str) -> None:
        self.db = db
        self.customer_id = customer_id
        self.role = role
        self.window = tk.Toplevel(parent)
        self.window.title(f"Customer {customer_id}")
        self.window.grab_set()
        self._create_widgets()
        self._load_customer()
        self._load_history()

    def _create_widgets(self) -> None:
        # Header for editing basic info
        header = ttk.Frame(self.window)
        header.pack(fill='x', padx=5, pady=5)
        ttk.Label(header, text="Name:").grid(row=0, column=0, sticky='w')
        self.name_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.name_var).grid(row=0, column=1, sticky='ew')
        ttk.Label(header, text="Phone:").grid(row=1, column=0, sticky='w')
        self.phone_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.phone_var).grid(row=1, column=1, sticky='ew')
        ttk.Label(header, text="Email:").grid(row=2, column=0, sticky='w')
        self.email_var = tk.StringVar()
        ttk.Entry(header, textvariable=self.email_var).grid(row=2, column=1, sticky='ew')
        header.columnconfigure(1, weight=1)
        # Save button
        self.save_btn = styled_button(header, text="Save", command=self._save_customer)
        self.save_btn.grid(row=0, column=2, rowspan=3, padx=5)
        # History label
        ttk.Label(self.window, text="Assignments & History:", font=('Arial', 10, 'bold')).pack(anchor='w', padx=5)
        # Treeview for history
        columns = ('serial', 'material_name', 'model', 'assigned_date', 'production_date', 'acquisition_date', 'status')
        self.history_tree = ttk.Treeview(self.window, columns=columns, show='headings', selectmode='extended')
        for col in columns:
            self.history_tree.heading(col, text=col.replace('_', ' ').capitalize())
            self.history_tree.column(col, anchor='w', stretch=True)
        self.history_tree.pack(fill='both', expand=True, padx=5, pady=5)
        # Actions
        actions = ttk.Frame(self.window)
        actions.pack(fill='x', padx=5, pady=5)
        self.assign_btn = styled_button(actions, text="Assign serials…", command=self._assign_serials_dialog)
        self.assign_btn.pack(side='left', padx=5)
        self.unassign_btn = styled_button(actions, text="Unassign selected", command=self._unassign_selected)
        self.unassign_btn.pack(side='left', padx=5)
        self.export_btn = styled_button(actions, text="Export history", command=self._export_history)
        self.export_btn.pack(side='left', padx=5)
        actions.pack_propagate(False)

        # Apply role restrictions: viewer cannot edit or assign/unassign
        if self.role == 'viewer':
            # disable editing fields and buttons except export
            self.save_btn.configure(state='disabled')
            self.assign_btn.configure(state='disabled')
            self.unassign_btn.configure(state='disabled')

    def _load_customer(self) -> None:
        cust = self.db.get_customer_by_id(self.customer_id)
        if not cust:
            messagebox.showerror("Error", f"Customer {self.customer_id} not found")
            self.window.destroy()
            return
        self.name_var.set(cust.get('name', ''))
        self.phone_var.set(cust.get('phone', '') or '')
        self.email_var.set(cust.get('email', '') or '')

    def _save_customer(self) -> None:
        try:
            self.db.update_customer(
                self.customer_id,
                name=self.name_var.get(),
                phone=self.phone_var.get() or None,
                email=self.email_var.get() or None
            )
            messagebox.showinfo("Saved", "Customer details saved.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save: {exc}")

    def _load_history(self) -> None:
        history = self.db.get_customer_history(self.customer_id)
        # clear
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for row in history:
            status = 'deleted' if row.get('deleted') else 'active'
            self.history_tree.insert('', 'end', values=(
                row['serial'], row['material_name'], row['material_model'], row['assigned_date'], row.get('production_date'), row.get('acquisition_date'), status
            ))

    def _assign_serials_dialog(self) -> None:
        # Ask user to paste serials
        serials_str = simpledialog.askstring("Assign Serials", "Enter serials separated by comma or newline:", parent=self.window)
        if not serials_str:
            return
        serials = [s.strip() for s in serials_str.replace(',', '\n').splitlines() if s.strip()]
        # resolve
        valid, invalid = self.db.resolve_serials_for_customer(serials)
        if invalid:
            messagebox.showwarning("Some serials invalid", f"These serials are invalid or already assigned: {', '.join(invalid)}")
        for serial in valid:
            try:
                self.db.assign_serial_to_customer(self.customer_id, serial)
            except Exception as exc:
                LOGGER.error("Failed to assign %s: %s", serial, exc)
        self._load_history()

    def _unassign_selected(self) -> None:
        items = self.history_tree.selection()
        if not items:
            return
        for item in items:
            serial = self.history_tree.item(item, 'values')[0]
            try:
                self.db.unassign_serial(serial, force=False)
            except Exception as exc:
                LOGGER.error("Failed to unassign %s: %s", serial, exc)
        self._load_history()

    def _export_history(self) -> None:
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            title="Export History",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            parent=self.window
        )
        if not file_path:
            return
        try:
            import csv
            history = self.db.get_customer_history(self.customer_id)
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['serial', 'material_name', 'material_model', 'assigned_date', 'production_date', 'acquisition_date', 'status'])
                for row in history:
                    status = 'deleted' if row.get('deleted') else 'active'
                    writer.writerow([
                        row['serial'], row['material_name'], row['material_model'], row['assigned_date'], row.get('production_date'), row.get('acquisition_date'), status
                    ])
            messagebox.showinfo("Exported", f"History exported to {file_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to export: {exc}")
