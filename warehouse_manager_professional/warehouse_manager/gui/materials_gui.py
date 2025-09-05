"""
Materials tabs for Inventory and Used items.

The InventoryTab and UsedTab present lists of materials, allow searching,
filtering by category, adding new materials, importing/exporting, and
opening detailed material windows. They share most of the code via
MaterialsTab base class.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import List, Optional

# Use absolute imports to allow running this script directly
from warehouse_manager.database import Database
from warehouse_manager.gui.theme import styled_button, make_thumbnail, THEME
from warehouse_manager.gui.material_details_gui import MaterialDetailsWindow


LOGGER = logging.getLogger(__name__)


class MaterialsTab:
    def __init__(self, parent: ttk.Notebook, db: Database, role: str, is_used: int = 0) -> None:
        self.db = db
        self.role = role
        self.is_used = is_used
        self.frame = ttk.Frame(parent)
        self._create_widgets()
        self.refresh()

    def _create_widgets(self) -> None:
        # Toolbar
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill='x')
        # Search
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        search_entry.bind('<Return>', lambda e: self.refresh())
        # Category filter
        ttk.Label(toolbar, text="Category:").pack(side='left', padx=(5,0))
        self.category_var = tk.StringVar()
        self.category_menu = ttk.Combobox(toolbar, textvariable=self.category_var, state='readonly')
        self.category_menu.pack(side='left', padx=5)
        self.category_menu.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        # Buttons
        self.add_btn = styled_button(toolbar, text="➕ Add Material", command=self._add_material_dialog)
        self.add_btn.pack(side='left', padx=5)
        self.import_btn = styled_button(toolbar, text="📥 Import…", command=self._import_materials)
        self.import_btn.pack(side='left', padx=5)
        self.export_btn = styled_button(toolbar, text="📤 Export…", command=self._export_materials)
        self.export_btn.pack(side='left', padx=5)
        self.refresh_btn = styled_button(toolbar, text="🔄 Refresh", command=self.refresh)
        self.refresh_btn.pack(side='left', padx=5)
        # Scrollable canvas for card grid
        self.canvas = tk.Canvas(self.frame, background=THEME['BG'], highlightthickness=0, borderwidth=0)
        # Vertical scrollbar
        self.vscroll = ttk.Scrollbar(self.frame, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        # Container frame inside canvas to hold cards
        self.card_container = ttk.Frame(self.canvas)
        # Create window on canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.card_container, anchor='nw')
        # Configure scrollregion whenever size of card_container changes
        def _on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
            # expand canvas width to fill available space
            self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())

        self.card_container.bind('<Configure>', _on_frame_configure)
        # Bind canvas resize to update card arrangement
        self.canvas.bind('<Configure>', lambda e: self.refresh())
        # Double click is replaced by clicking on card; still keep for fallback
        # self.tree.bind('<Double-1>', self._on_double_click)

        # Apply role restrictions: viewer cannot add/import/export materials
        if self.role == 'viewer':
            self.add_btn.configure(state='disabled')
            self.import_btn.configure(state='disabled')
            self.export_btn.configure(state='disabled')

    def refresh(self) -> None:
        # Populate categories
        cats = self.db.get_dynamic_categories() + self.db.get_all_categories()
        cats = sorted(set(cats))
        current = self.category_var.get()
        self.category_menu['values'] = [''] + cats
        if current not in cats:
            self.category_var.set('')
        # Get materials
        query = self.search_var.get().strip()
        category = self.category_var.get() or None
        materials = self.db.get_all_materials(is_used=self.is_used, name_query=query or None, category=category)
        # Clear existing cards
        for child in self.card_container.winfo_children():
            child.destroy()
        # Determine number of columns based on available width
        try:
            width = self.canvas.winfo_width() or self.frame.winfo_width() or 800
        except Exception:
            width = 800
        card_width = 280  # approximate width per card including padding
        cols = max(1, width // card_width)
        # Create cards for each material
        for index, mat in enumerate(materials):
            row = index // cols
            col = index % cols
            # Card frame
            card = ttk.Frame(self.card_container, style='Card.TFrame', padding=(10, 10))
            card.grid(row=row, column=col, padx=10, pady=10, sticky='n')
            # Thumbnail image; use larger size for materials
            thumb = make_thumbnail(mat.get('image_path'), size=(96, 96))
            img_label = ttk.Label(card, image=thumb, style='Card.TLabel')
            img_label.image = thumb  # prevent garbage collection
            img_label.pack(side='top', anchor='center')
            # Name and model
            name_label = ttk.Label(card, text=mat['name'], style='CardTitle.TLabel', wraplength=240, justify='center')
            name_label.pack(side='top', anchor='center', pady=(5, 0))
            model_label = ttk.Label(card, text=mat['model'], style='CardSubtitle.TLabel', wraplength=240, justify='center')
            model_label.pack(side='top', anchor='center', pady=(0, 2))
            # Category and counts
            cat_text = mat.get('category') or mat.get('auto_category') or '—'
            cat_label = ttk.Label(card, text=f"{cat_text}", style='CardSubtitle.TLabel')
            cat_label.pack(side='top', anchor='center', pady=(0, 2))
            counts_text = f"Avail: {mat.get('available_serials')}/{mat.get('total_serials')}"
            counts_label = ttk.Label(card, text=counts_text, style='CardSubtitle.TLabel')
            counts_label.pack(side='top', anchor='center')
            # Click binding: open details on click
            def open_details(event, material_id=mat['id']):
                MaterialDetailsWindow(self.frame, self.db, material_id, self.role)

            card.bind('<Button-1>', open_details)
            img_label.bind('<Button-1>', open_details)
            name_label.bind('<Button-1>', open_details)
            model_label.bind('<Button-1>', open_details)
            cat_label.bind('<Button-1>', open_details)
            counts_label.bind('<Button-1>', open_details)

    def _on_double_click(self, event) -> None:
        item_id = self.tree.selection()
        if not item_id:
            return
        values = self.tree.item(item_id[0], 'values')
        material_id = int(values[0])
        MaterialDetailsWindow(self.frame, self.db, material_id)

    def _add_material_dialog(self) -> None:
        # Ask for basic fields
        name = simpledialog.askstring("Material Name", "Enter material name:", parent=self.frame)
        if not name:
            return
        model = simpledialog.askstring("Material Model", "Enter model:", parent=self.frame)
        if not model:
            return
        producer = simpledialog.askstring("Producer", "Enter producer (optional):", parent=self.frame)
        description = simpledialog.askstring("Description", "Enter description (optional):", parent=self.frame)
        price = simpledialog.askfloat("Retail price", "Enter price (optional):", parent=self.frame, minvalue=0.0)
        warranty = simpledialog.askinteger("Warranty months", "Enter warranty duration in months (optional):", parent=self.frame, minvalue=0)
        try:
            material_id = self.db.add_material(name, model, producer, description, None, price, self.is_used, warranty)
            # Autocategorize this material
            self.db.autocategorize_material(material_id)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to add material: {exc}")

    def _import_materials(self) -> None:
        file_path = filedialog.askopenfilename(title="Import Materials", filetypes=[("CSV","*.csv"), ("Excel","*.xlsx;*.xls"), ("All","*.*")], parent=self.frame)
        if not file_path:
            return
        from warehouse_manager.excel_import_export import import_materials
        try:
            count = import_materials(self.db, file_path, is_used=self.is_used)
            messagebox.showinfo("Import", f"Imported {count} materials from {file_path}")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to import: {exc}")

    def _export_materials(self) -> None:
        file_path = filedialog.asksaveasfilename(title="Export Materials", defaultextension=".csv", filetypes=[("CSV","*.csv"),("All","*.*")], parent=self.frame)
        if not file_path:
            return
        from warehouse_manager.excel_import_export import export_materials
        try:
            count = export_materials(self.db, file_path, is_used=self.is_used)
            messagebox.showinfo("Export", f"Exported {count} materials to {file_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to export: {exc}")


class InventoryTab(MaterialsTab):
    def __init__(self, parent: ttk.Notebook, db: Database, role: str) -> None:
        super().__init__(parent, db, role, is_used=0)


class UsedTab(MaterialsTab):
    def __init__(self, parent: ttk.Notebook, db: Database, role: str) -> None:
        super().__init__(parent, db, role, is_used=1)
