"""Company details printed on every invoice.

These defaults are placeholders. Put the real details in instance/company.json
(same keys), which is kept out of git.
"""

import json
from pathlib import Path

DEFAULT_COMPANY = {
    "name": "Example Lettings Ltd",
    "address": ["Example Farm", "Sample Lane", "Anytown", "Countyshire AB1 2CD"],
    "tel": "01234 567890",
    "vat_reg": "000 0000 00",
    "bank": [
        "Bank details for direct debit payment: Example Bank plc,",
        "Sort code: 00-00-00 Account Number: 00000000",
        "Account name: Example Lettings Ltd",
    ],
    "correspondence_heading": "Please send any written correspondence including cheques to:",
    "correspondence": "1 Example Road, Anytown, Countyshire AB1 2CD",
    # Copied in on every email draft (the VBA CC'd the company address). Empty for none.
    "email_cc": "",
}


def load_company(instance_path: str) -> dict:
    path = Path(instance_path) / "company.json"
    company = dict(DEFAULT_COMPANY)
    if path.exists():
        company.update(json.loads(path.read_text(encoding="utf-8")))
    return company
