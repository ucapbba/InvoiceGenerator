"""Draw an invoice PDF laid out like the 'Invoice Template Units/Houses' sheets.

Positions use the template's own grid: columns A-I (widths taken from the sheet)
and rows 1-27, so cell references in the comments match the spreadsheet.
"""

from datetime import date
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .generator import money, split_address

PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP = 50, 60
ROW_H = 18
FONT, FONT_BOLD, SIZE = "Helvetica", "Helvetica-Bold", 12

# Excel column widths (in characters) from the template.
_COL_WIDTHS = [("A", 4.9), ("B", 8.43), ("C", 8.6), ("D", 5.1), ("E", 19.0), ("F", 0.3), ("G", 0.9), ("H", 12.0), ("I", 11.4)]


def _column_edges():
    pixels = [width * 7 + 5 for _, width in _COL_WIDTHS]
    scale = (PAGE_W - 2 * MARGIN_X) / sum(pixels)
    edges, x = {}, MARGIN_X
    for (col, _), px in zip(_COL_WIDTHS, pixels):
        edges[col] = x
        x += px * scale
    edges["end"] = x
    return edges


COL = _column_edges()
_NEXT = {"A": "B", "B": "C", "C": "D", "D": "E", "E": "F", "F": "G", "G": "H", "H": "I", "I": "end"}


def _row_top(row):
    return PAGE_H - MARGIN_TOP - (row - 1) * ROW_H


def _text(c, col, row, text, bold=False, max_right=None):
    """Write text in a cell, shrinking it if it would run past max_right."""
    font = FONT_BOLD if bold else FONT
    x = COL[col] + 3
    size = SIZE
    if max_right is not None:
        while size > 7 and x + stringWidth(text, font, size) > max_right - 3:
            size -= 0.5
    c.setFont(font, size)
    c.drawString(x, _row_top(row) - ROW_H + 5, text)


def _box(c, first_col, last_col, row):
    x0, x1 = COL[first_col], COL[_NEXT[last_col]]
    c.rect(x0, _row_top(row) - ROW_H, x1 - x0, ROW_H)


def render_invoice(invoice, company) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Invoice {invoice['invoice_id']}")
    c.setAuthor(company["name"])
    c.setLineWidth(0.75)

    # A1:D1 / E1 - invoice number; A3:D3 - VAT registration.
    _box(c, "A", "D", 1)
    _box(c, "E", "E", 1)
    _text(c, "A", 1, "STATEMENT/INVOICE No.")
    _text(c, "E", 1, invoice["invoice_id"], max_right=COL["F"])
    _box(c, "A", "D", 3)
    _text(c, "A", 3, f"VAT Reg. No. {company['vat_reg']}")

    # A5 onwards - client name and address, one comma-separated part per row.
    _text(c, "A", 5, invoice["client"], max_right=COL["H"])
    for offset, line in enumerate(split_address(invoice["address"]), start=1):
        _text(c, "A", 5 + offset, line, max_right=COL["H"])

    # H5 onwards - company name, address, phone, then the invoice date (H12 in the template).
    company_lines = [company["name"], *company["address"], f"Tel: {company['tel']}"]
    for offset, line in enumerate(company_lines):
        _text(c, "H", 5 + offset, line, max_right=COL["end"] + MARGIN_X - 10)
    _text(c, "H", 5 + len(company_lines), date.fromisoformat(invoice["invoice_date"]).strftime("%d/%m/%Y"))

    # Rows 16-20 - charge line and totals. Houses have no VAT column.
    is_unit = invoice["type"] == "Unit"
    if is_unit:
        _text(c, "H", 16, "VAT £")
    _text(c, "I", 16, "NET £")
    line_y = _row_top(17)
    c.line(COL["A"], line_y, COL["end"], line_y)
    _text(c, "A", 17, invoice["property"], max_right=COL["H"])
    if is_unit:
        _text(c, "H", 17, money(invoice["vat"]))
    _text(c, "I", 17, money(invoice["net"]))
    _text(c, "E", 20, "TOTAL INVOICE")
    _text(c, "I", 20, money(invoice["total"]))

    # Rows 22 onwards - payment details and correspondence address.
    row = 22
    for line in company["bank"]:
        _text(c, "A", row, line, max_right=COL["end"])
        row += 1
    row += 1
    _text(c, "A", row, company["correspondence_heading"], bold=True, max_right=COL["end"])
    _text(c, "A", row + 1, company["correspondence"], max_right=COL["end"])

    c.showPage()
    c.save()
    return buf.getvalue()
