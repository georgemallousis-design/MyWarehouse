"""
Import and export helpers for materials and serials.

Uses pandas for CSV/Excel import/export. If pandas is not installed,
falls back to the csv module for CSV only.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

try:
    import pandas as pd  # type: ignore
except ImportError:
    pd = None  # type: ignore

from warehouse_manager.database import Database


LOGGER = logging.getLogger(__name__)


def import_materials(db: Database, file_path: str, is_used: int = 0) -> int:
    """
    Import materials from CSV or Excel. Expected columns: name, model, producer, description, image_path,
    retail_price, warranty_months, serials (optional comma/newline separated list) .
    Returns number of materials created.
    """
    path = Path(file_path)
    if pd and path.suffix.lower() in {'.xlsx', '.xls'}:
        df = pd.read_excel(file_path)
    else:
        df = None
    if df is None:
        # use csv reader
        rows = []
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    else:
        rows = df.to_dict(orient='records')
    count = 0
    for row in rows:
        try:
            name = row.get('name')
            model = row.get('model')
            if not name or not model:
                continue
            producer = row.get('producer') or None
            description = row.get('description') or None
            price = row.get('retail_price') or row.get('price')
            try:
                price_val = float(price) if price is not None else None
            except Exception:
                price_val = None
            warranty = row.get('warranty_months') or row.get('warranty')
            try:
                warranty_val = int(warranty) if warranty is not None else None
            except Exception:
                warranty_val = None
            material_id = db.add_material(name, model, producer, description, None, price_val, is_used, warranty_val)
            # import serials if any
            serials_field = row.get('serials') or row.get('serial')
            if serials_field:
                serials = [s.strip() for s in str(serials_field).replace(',', '\n').splitlines() if s.strip()]
                db.add_serials_to_material(material_id, serials)
            db.autocategorize_material(material_id)
            count += 1
        except Exception as exc:
            LOGGER.error("Failed to import row %s: %s", row, exc)
    return count


def export_materials(db: Database, file_path: str, is_used: int = 0) -> int:
    """Export materials to CSV. Returns number of rows exported."""
    materials = db.get_all_materials(is_used=is_used)
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # header
        writer.writerow([
            'id', 'name', 'model', 'producer', 'description', 'retail_price', 'is_used', 'warranty_months',
            'category', 'auto_category', 'auto_confidence', 'model_family', 'available_serials', 'total_serials'
        ])
        for mat in materials:
            writer.writerow([
                mat['id'], mat['name'], mat['model'], mat.get('producer'), mat.get('description'), mat.get('retail_price'),
                mat.get('is_used'), mat.get('warranty_months'), mat.get('category'), mat.get('auto_category'), mat.get('auto_confidence'), mat.get('model_family'),
                mat.get('available_serials'), mat.get('total_serials')
            ])
    return len(materials)
