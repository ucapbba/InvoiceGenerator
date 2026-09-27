"""Invoice rules ported from the Excel VBA generator (Generator.bas, Common.bas).

Differences from the VBA, fixing known bugs:
- Invoice numbers are always three digits (10-2023-010, not 10-2023-0010).
- Numbering starts at 001, not 000.
- Every row is checked before anything is generated, so a bad row can't leave
  a half-finished batch behind.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

VAT_RATE = Decimal("0.20")
TYPES = ("Unit", "House")
PENNY = Decimal("0.01")
EMAIL_RE = re.compile(r"^[^@\s,;?&]+@[^@\s,;?&]+\.[^@\s,;?&]+$")


class GenerationError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def surname(full_name: str) -> str:
    """GetSurname: the last word of "Title Firstname Lastname"."""
    parts = full_name.split()
    if len(parts) < 2:
        raise ValueError(f"name '{full_name}' should be 'Title Firstname Lastname'")
    return parts[-1]


def sheet_name(base: str, taken: set[str]) -> tuple[str, int]:
    """Smith, then Smith1, Smith2... Returns the name and its count (the VBA 'Count' column)."""
    name, count = base, 0
    while name in taken:
        count += 1
        name = f"{base}{count}"
    return name, count


def invoice_id(invoice_date: date, number: int) -> str:
    return f"{invoice_date.month}-{invoice_date.year}-{number:03d}"


def parse_amount(text: str) -> Decimal:
    cleaned = text.replace("£", "").replace(",", "").strip()
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"amount '{text}' is not a number") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"amount '{text}' must be zero or more")
    return amount.quantize(PENNY, ROUND_HALF_UP)


def split_address(address: str) -> list[str]:
    return [part.strip() for part in address.split(",") if part.strip()]


def totals(net: Decimal, invoice_type: str) -> tuple[Decimal, Decimal]:
    """(vat, total). Units carry 20% VAT; Houses don't (as in the two templates)."""
    vat = (net * VAT_RATE).quantize(PENNY, ROUND_HALF_UP) if invoice_type == "Unit" else Decimal("0.00")
    return vat, net + vat


def build_invoices(rows, invoice_date: date, next_number: int, taken=()):
    """Generate_Click: one invoice per client row. Blank rows are skipped.

    Returns (invoices, next_number_after). Raises GenerationError listing every
    problem row, in which case nothing should be saved.
    """
    errors, invoices = [], []
    taken = set(taken)
    number = next_number
    for position, row in enumerate(rows, start=1):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        label = f"Row {position} ({name})"
        try:
            base = surname(name)
            net = parse_amount(row.get("amount") or "")
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        invoice_type = row.get("type") or ""
        if invoice_type not in TYPES:
            errors.append(f"{label}: type must be Unit or House")
            continue
        email = (row.get("email") or "").strip()
        if email and not EMAIL_RE.match(email):
            errors.append(f"{label}: email '{email}' doesn't look right")
            continue

        name_on_sheet, count = sheet_name(base, taken)
        taken.add(name_on_sheet)
        vat, total = totals(net, invoice_type)
        invoices.append({
            "client_id": row.get("id"),
            "sheet_name": name_on_sheet,
            "count": count,
            "invoice_id": invoice_id(invoice_date, number),
            "invoice_date": invoice_date.isoformat(),
            "client": name,
            "address": (row.get("address") or "").strip(),
            "property": (row.get("property") or "").strip(),
            "type": invoice_type,
            "email": email,
            "net": str(net),
            "vat": str(vat),
            "total": str(total),
        })
        number += 1

    if errors:
        raise GenerationError(errors)
    if not invoices:
        raise GenerationError(["There are no clients to invoice - add a name to at least one row."])
    return invoices, number


def can_email(invoice) -> bool:
    """SendEmail only drafts emails for Units with an email address."""
    return invoice["type"] == "Unit" and bool(invoice["email"])


def email_subject(invoice) -> str:
    return f"Invoice {invoice['invoice_id']}"


def email_body(invoice, company) -> str:
    return (
        f"Dear {invoice['client']},\n\n"
        f"Attached is your invoice {invoice['invoice_id']} for {invoice['property']}.\n\n"
        f"Regards,\n{company['name']}"
    )


def money(value) -> str:
    return f"£{Decimal(value):,.2f}"
