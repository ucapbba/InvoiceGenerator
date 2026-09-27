from datetime import date
from decimal import Decimal

import pytest

from invoicegen import generator as gen


def row(name="Mr A Smith", amount="100", invoice_type="Unit", email="", **extra):
    return {"name": name, "amount": amount, "type": invoice_type, "email": email,
            "property": extra.get("property", "Unit 1"), "address": extra.get("address", "1 Road,Town")}


def test_surname_is_last_word():
    assert gen.surname("Ms C Burns") == "Burns"
    assert gen.surname("Mr John Paul Smith") == "Smith"


def test_surname_rejects_single_word():
    with pytest.raises(ValueError):
        gen.surname("Burns")


def test_duplicate_surnames_get_counts():
    invoices, _ = gen.build_invoices([row("Mr A Smith"), row("Mrs B Smith"), row("Dr C Smith")], date(2026, 10, 1), 1)
    assert [(i["sheet_name"], i["count"]) for i in invoices] == [("Smith", 0), ("Smith1", 1), ("Smith2", 2)]


def test_invoice_ids_are_three_digits_from_the_date():
    invoices, next_number = gen.build_invoices([row(f"Mr A Person{i}") for i in range(11)], date(2026, 3, 5), 1)
    assert invoices[0]["invoice_id"] == "3-2026-001"
    assert invoices[9]["invoice_id"] == "3-2026-010"
    assert next_number == 12


def test_units_have_vat_houses_do_not():
    unit, house = gen.build_invoices([row(amount="333.33"), row("Mr B Jones", amount="£1,000", invoice_type="House")],
                                     date(2026, 10, 1), 1)[0]
    assert (unit["net"], unit["vat"], unit["total"]) == ("333.33", "66.67", "400.00")
    assert (house["net"], house["vat"], house["total"]) == ("1000.00", "0.00", "1000.00")


def test_blank_rows_are_skipped():
    invoices, _ = gen.build_invoices([row(), {"name": "  ", "amount": ""}, row("Mr B Jones")], date(2026, 10, 1), 1)
    assert len(invoices) == 2


def test_errors_are_collected_and_nothing_is_generated():
    rows = [row(), row("Jones"), row("Mr C Brown", amount="abc"), row("Mr D Green", email="not an email")]
    with pytest.raises(gen.GenerationError) as exc:
        gen.build_invoices(rows, date(2026, 10, 1), 1)
    assert len(exc.value.errors) == 3
    assert exc.value.errors[0].startswith("Row 2 (Jones)")


def test_negative_amounts_are_rejected():
    with pytest.raises(gen.GenerationError):
        gen.build_invoices([row(amount="-5")], date(2026, 10, 1), 1)


def test_address_parts_are_trimmed():
    assert gen.split_address("19 Bury Road, Ramsey, , PE26 1NE") == ["19 Bury Road", "Ramsey", "PE26 1NE"]


def test_only_units_with_email_are_emailed():
    assert gen.can_email({"type": "Unit", "email": "a@example.com"})
    assert not gen.can_email({"type": "House", "email": "a@example.com"})
    assert not gen.can_email({"type": "Unit", "email": ""})


def test_money():
    assert gen.money(Decimal("1234.5")) == "£1,234.50"
