"""
Detailed window for editing materials and managing serial numbers.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import List, Optional

from warehouse_manager.database import Database
from warehouse_manager.gui.theme import styled_button, make_thumbnail, THEME


LOGGER = logging.getLogger(__name__)


class MaterialDetailsWindow:
    def __init__(self, parent: tk.Widget, db: Database, material_id: int, role: str) -> None:
        self.db = db
        self.material_id = material_id
        self.role = role
        self.window = tk.Toplevel(parent)
        self.window.title(f"Material {material_id}")
        self.window.grab_set()
        self._create_widgets()
        self._load_material()
        self._load_serials()

    def _create_widgets(self) -> None:
        # Header with image preview and editable fields
        header = ttk.Frame(self.window)
        header.pack(fill='x', padx=5, pady=5)
        # Left panel: image preview and picker
        left_panel = ttk.Frame(header)
        left_panel.pack(side='left', padx=(0, 10))
        # Placeholder thumbnail until loaded
        self._current_thumb = make_thumbnail(None, size=(96, 96))
        self.image_label = ttk.Label(left_panel, image=self._current_thumb)
        self.image_label.image = self._current_thumb
        self.image_label.pack()
        image_btn = styled_button(left_panel, text="🖼 Image", command=self._pick_image)
        image_btn.pack(pady=(5, 0))
        # Right panel: fields and actions
        right_panel = ttk.Frame(header)
        right_panel.pack(side='left', fill='x', expand=True)
        # Name
        ttk.Label(right_panel, text="Name:").grid(row=0, column=0, sticky='w')
        self.name_var = tk.StringVar()
        ttk.Entry(right_panel, textvariable=self.name_var).grid(row=0, column=1, sticky='ew')
        # Model
        ttk.Label(right_panel, text="Model:").grid(row=1, column=0, sticky='w')
        self.model_var = tk.StringVar()
        ttk.Entry(right_panel, textvariable=self.model_var).grid(row=1, column=1, sticky='ew')
        # Producer
        ttk.Label(right_panel, text="Producer:").grid(row=2, column=0, sticky='w')
        self.producer_var = tk.StringVar()
        ttk.Entry(right_panel, textvariable=self.producer_var).grid(row=2, column=1, sticky='ew')
        # Price
        ttk.Label(right_panel, text="Price:").grid(row=3, column=0, sticky='w')
        self.price_var = tk.DoubleVar()
        ttk.Entry(right_panel, textvariable=self.price_var).grid(row=3, column=1, sticky='ew')
        # Warranty months
        ttk.Label(right_panel, text="Warranty (mo):").grid(row=4, column=0, sticky='w')
        self.warranty_var = tk.StringVar()
        ttk.Entry(right_panel, textvariable=self.warranty_var).grid(row=4, column=1, sticky='ew')
        # Category (manual override)
        ttk.Label(right_panel, text="Category (opt):").grid(row=5, column=0, sticky='w')
        self.category_var = tk.StringVar()
        self.category_entry = ttk.Entry(right_panel, textvariable=self.category_var)
        self.category_entry.grid(row=5, column=1, sticky='ew')
        # Buttons for save/auto categories in right panel
        self.save_btn = styled_button(right_panel, text="💾 Save", command=self._save_material)
        self.save_btn.grid(row=0, column=2, rowspan=3, padx=5, pady=2, sticky='ns')
        self.auto_btn = styled_button(right_panel, text="🧠 Auto", command=self._auto_categorize)
        self.auto_btn.grid(row=3, column=2, rowspan=3, padx=5, pady=2, sticky='ns')
        right_panel.columnconfigure(1, weight=1)
        # Info area for auto category and confidence
        self.auto_label = ttk.Label(self.window, text="")
        self.auto_label.pack(anchor='w', padx=5)
        # Serials list
        columns = ('serial', 'production_date', 'acquisition_date', 'price', 'assigned_to')
        self.serials_tree = ttk.Treeview(self.window, columns=columns, show='headings', selectmode='extended')
        for col in columns:
            self.serials_tree.heading(col, text=col.replace('_', ' ').capitalize())
            self.serials_tree.column(col, anchor='w', stretch=True)
        # Row tags for alternating backgrounds
        self.serials_tree.tag_configure('oddrow', background=THEME['ALT_BG'])
        self.serials_tree.tag_configure('evenrow', background=THEME['CARD_BG'])
        self.serials_tree.pack(fill='both', expand=True, padx=5, pady=5)
        # Buttons for serials
        serial_actions = ttk.Frame(self.window)
        serial_actions.pack(fill='x', padx=5, pady=5)
        self.add_serial_btn = styled_button(serial_actions, text="➕ Add Serials", command=self._add_serials_dialog)
        self.add_serial_btn.pack(side='left', padx=5)
        self.assign_btn = styled_button(serial_actions, text="⇢ Assign", command=self._assign_selected_serials)
        self.assign_btn.pack(side='left', padx=5)
        self.unassign_btn = styled_button(serial_actions, text="⇠ Unassign", command=self._unassign_selected_serials)
        self.unassign_btn.pack(side='left', padx=5)
        self.move_btn = styled_button(serial_actions, text="⬇ Move to Used", command=self._move_selected_to_used)
        self.move_btn.pack(side='left', padx=5)
        self.delete_btn = styled_button(serial_actions, text="🗑️ Delete", command=self._delete_selected_serials)
        self.delete_btn.pack(side='left', padx=5)

        # Apply role restrictions
        if self.role == 'viewer':
            # Viewer cannot modify anything: disable all actions and category editing
            for widget in [self.save_btn, self.auto_btn, self.add_serial_btn, self.assign_btn,
                           self.unassign_btn, self.move_btn, self.delete_btn, self.category_entry]:
                widget.configure(state='disabled')
        elif self.role == 'operator':
            # Operator can edit and assign/unassign but cannot delete serials
            self.delete_btn.configure(state='disabled')

    def _load_material(self) -> None:
        # load material info
        mats = self.db.get_all_materials(is_used=None, name_query=None)
        mat = None
        for m in mats:
            if m['id'] == self.material_id:
                mat = m
                break
        if not mat:
            messagebox.showerror("Error", f"Material {self.material_id} not found")
            self.window.destroy()
            return
        self.name_var.set(mat['name'])
        self.model_var.set(mat['model'])
        self.producer_var.set(mat.get('producer') or '')
        self.price_var.set(mat.get('retail_price') or 0.0)
        self.warranty_var.set(str(mat.get('warranty_months') or ''))
        self.category_var.set(mat.get('category') or '')
        auto_cat = mat.get('auto_category')
        conf = mat.get('auto_confidence')
        family = mat.get('model_family')
        auto_text = f"Auto category: {auto_cat} (conf={conf:.2f}) family={family}" if auto_cat else "Auto category: —"
        self.auto_label.configure(text=auto_text)
        # Update image preview
        path = mat.get('image_path')
        thumb = make_thumbnail(path, size=(96, 96))
        self.image_label.configure(image=thumb)
        self.image_label.image = thumb

    def _load_serials(self) -> None:
        serials = self.db.get_serials_by_material(self.material_id, include_assigned=True)
        # clear
        for item in self.serials_tree.get_children():
            self.serials_tree.delete(item)
        for idx, s in enumerate(serials):
            tag = 'oddrow' if idx % 2 else 'evenrow'
            self.serials_tree.insert('', 'end', values=(
                s['serial'], s.get('production_date'), s.get('acquisition_date'), s.get('retail_price'), s.get('assigned_to') or ''
            ), tags=(tag,))

    def _save_material(self) -> None:
        fields = {
            'name': self.name_var.get(),
            'model': self.model_var.get(),
            'producer': self.producer_var.get() or None,
            'retail_price': float(self.price_var.get()) if self.price_var.get() else None,
            'warranty_months': int(self.warranty_var.get()) if self.warranty_var.get() else None,
            'category': self.category_var.get() or None,
        }
        try:
            self.db.set_material_fields(self.material_id, **fields)
            # If category changed, update local auto label
            self._load_material()
            messagebox.showinfo("Saved", "Material updated")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save: {exc}")

    def _pick_image(self) -> None:
        """Prompt user to select an image file and store its path for this material."""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp"), ("All Files", "*.*")],
            parent=self.window
        )
        if not file_path:
            return
        from pathlib import Path
        import shutil
        # Determine destination directory relative to database file
        db_dir = Path(self.db.path).resolve().parent
        images_dir = db_dir / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        # Copy the selected file to images dir with a unique name
        try:
            src = Path(file_path)
            dest = images_dir / src.name
            # If destination exists, create unique file name
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                i = 1
                while True:
                    new_dest = images_dir / f"{stem}_{i}{suffix}"
                    if not new_dest.exists():
                        dest = new_dest
                        break
                    i += 1
            shutil.copy(src, dest)
            # Update DB with new image_path
            self.db.set_material_fields(self.material_id, image_path=str(dest))
            # Reload material to update preview
            self._load_material()
            messagebox.showinfo("Image Set", f"Image set for material. Saved as {dest.name}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to copy image: {exc}")

    def _auto_categorize(self) -> None:
        try:
            mat = self.db.autocategorize_material(self.material_id)
            self._load_material()
            messagebox.showinfo("Auto categorized", f"Auto category: {mat['auto_category']} (conf={mat['auto_confidence']:.2f})")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to auto categorize: {exc}")

    def _add_serials_dialog(self) -> None:
        serials_str = simpledialog.askstring("Add Serials", "Enter serials separated by comma or newline:", parent=self.window)
        if not serials_str:
            return
        serials = [s.strip() for s in serials_str.replace(',', '\n').splitlines() if s.strip()]
        prod_date = simpledialog.askstring("Production date", "Enter production date (YYYY-MM-DD, optional):", parent=self.window)
        acq_date = simpledialog.askstring("Acquisition date", "Enter acquisition date (YYYY-MM-DD, optional):", parent=self.window)
        try:
            self.db.add_serials_to_material(self.material_id, serials, production_date=prod_date or None, acquisition_date=acq_date or None)
            self._load_serials()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to add serials: {exc}")

    def _selected_serials(self) -> List[str]:
        items = self.serials_tree.selection()
        return [self.serials_tree.item(item, 'values')[0] for item in items]

    def _assign_selected_serials(self) -> None:
        serials = self._selected_serials()
        if not serials:
            return
        # Prompt for the 4‑digit PIN used as the customer identifier
        customer_id = simpledialog.askstring("Assign to Customer", "Enter customer PIN:", parent=self.window)
        if not customer_id:
            return
        for serial in serials:
            try:
                self.db.assign_serial_to_customer(customer_id, serial)
            except Exception as exc:
                LOGGER.error("Failed to assign %s: %s", serial, exc)
        self._load_serials()

    def _unassign_selected_serials(self) -> None:
        serials = self._selected_serials()
        if not serials:
            return
        for serial in serials:
            try:
                self.db.unassign_serial(serial)
            except Exception as exc:
                LOGGER.error("Failed to unassign %s: %s", serial, exc)
        self._load_serials()

    def _move_selected_to_used(self) -> None:
        serials = self._selected_serials()
        if not serials:
            return
        confirm = messagebox.askyesno("Confirm", f"Move {len(serials)} serial(s) to used stock?", parent=self.window)
        if not confirm:
            return
        try:
            self.db.transfer_serials_to_used(serials)
            self._load_serials()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to move: {exc}")

    def _delete_selected_serials(self) -> None:
        serials = self._selected_serials()
        if not serials:
            return
        confirm = messagebox.askyesno("Confirm", f"Delete {len(serials)} serial(s)? This is permanent.", parent=self.window)
        if not confirm:
            return
        try:
            self.db.delete_serials(serials)
            self._load_serials()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to delete: {exc}")
