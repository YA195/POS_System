"""Printer utilities for receipt and barcode printing."""
import win32print
import win32ui
from datetime import datetime

try:
    import barcode
    from barcode.writer import ImageWriter
    from PIL import Image, ImageDraw, ImageFont, ImageWin
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("Warning: python-barcode and/or PIL not available. Barcode printing will use text only.")


def get_available_printers():
    """Get list of available printers."""
    return [printer[2] for printer in win32print.EnumPrinters(2)]


def print_receipt(printer_name, sale_data, settings):
    """Print a sale receipt."""
    # Implementation moved from app.py
    # This would contain the full printing logic
    pass


def print_barcode(printer_name, barcode_data):
    """Print barcodes."""
    # Implementation moved from app.py
    # This would contain the barcode printing logic
    pass


def print_shift_summary(printer_name, shift_data, settings):
    """Print shift summary report."""
    # Implementation moved from app.py
    # This would contain the shift summary printing logic
    pass
