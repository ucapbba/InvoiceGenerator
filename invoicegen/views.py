"""The Generator page and its buttons: Save, Add row, Generate, Clear invoices, PDF, Export."""

import zipfile
from datetime import date
from io import BytesIO

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, send_file, url_for

from . import generator
from .db import get_db, get_settings, set_setting
from .pdf import render_invoice

MAX_ROWS = 200
FIELD_LIMITS = {"name": 100, "amount": 20, "property": 150, "address": 300, "email": 150}

bp = Blueprint("views", __name__)


@bp.before_request
def _require_login():
    if g.user is None:
        return redirect(url_for("auth.login"))


def _clients(db):
    return db.execute("SELECT * FROM clients ORDER BY position, id").fetchall()


def _invoice(db, invoice_pk):
    row = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_pk,)).fetchone()
    if row is None:
        flash("That invoice no longer exists - it may have been cleared.", "error")
    return row


@bp.get("/", endpoint="generator")
def generator_page():
    db = get_db()
    settings = get_settings(db)
    company = current_app.config["COMPANY"]
    invoices = []
    for row in db.execute("SELECT * FROM invoices ORDER BY id"):
        inv = dict(row)
        inv["total_display"] = generator.money(inv["total"])
        inv["email_ok"] = generator.can_email(inv)
        inv["subject"] = generator.email_subject(inv)
        inv["body"] = generator.email_body(inv, company)
        invoices.append(inv)
    return render_template(
        "generator.html",
        settings=settings,
        next_id=generator.invoice_id(date.fromisoformat(settings["invoice_date"]), int(settings["next_number"])),
        clients=_clients(db),
        invoices=invoices,
        types=generator.TYPES,
    )


def _save_settings(db):
    try:
        invoice_date = date.fromisoformat(request.form.get("invoice_date", ""))
        set_setting(db, "invoice_date", invoice_date.isoformat())
    except ValueError:
        flash("The date wasn't valid, so it wasn't changed.", "error")
    try:
        next_number = int(request.form.get("next_number", ""))
        if next_number < 1:
            raise ValueError
        set_setting(db, "next_number", next_number)
    except ValueError:
        flash("The next invoice number must be a whole number of 1 or more.", "error")


def _save_rows(db):
    form = request.form
    columns = {field: form.getlist(field) for field in ("id", "name", "amount", "property", "address", "type", "email")}
    for i, row_id in enumerate(columns["id"]):
        values = {field: (columns[field][i] if i < len(columns[field]) else "") for field in columns}
        for field, limit in FIELD_LIMITS.items():
            values[field] = values[field].strip()[:limit]
        if values["type"] not in generator.TYPES:
            values["type"] = "Unit"
        db.execute(
            "UPDATE clients SET name = ?, amount = ?, property = ?, address = ?, type = ?, email = ? WHERE id = ?",
            (values["name"], values["amount"], values["property"], values["address"], values["type"], values["email"], row_id),
        )


def _generate(db):
    if db.execute("SELECT 1 FROM invoices LIMIT 1").fetchone():
        flash("Please clear existing invoices before generating.", "error")
        return False
    settings = get_settings(db)
    try:
        invoices, next_number = generator.build_invoices(
            [dict(row) for row in _clients(db)],
            date.fromisoformat(settings["invoice_date"]),
            int(settings["next_number"]),
        )
    except generator.GenerationError as exc:
        for message in exc.errors:
            flash(message, "error")
        flash("No invoices were generated - fix the rows above and try again.", "error")
        return False
    for inv in invoices:
        db.execute(
            "INSERT INTO invoices (sheet_name, invoice_id, invoice_date, client, address, property, type, email, net, vat, total, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inv["sheet_name"], inv["invoice_id"], inv["invoice_date"], inv["client"], inv["address"], inv["property"],
             inv["type"], inv["email"], inv["net"], inv["vat"], inv["total"], g.user["username"]),
        )
        db.execute("UPDATE clients SET count = ? WHERE id = ?", (inv["count"], inv["client_id"]))
    set_setting(db, "next_number", next_number)
    flash(f"Generated {len(invoices)} invoice{'s' if len(invoices) != 1 else ''}.", "success")
    return True


@bp.post("/sheet")
def sheet():
    """Every button on the Generator form saves the sheet first, then does its action."""
    db = get_db()
    _save_settings(db)
    _save_rows(db)
    action = request.form.get("action", "save")
    delete_id = request.form.get("delete")
    anchor = None

    if delete_id:
        db.execute("DELETE FROM clients WHERE id = ?", (delete_id,))
        flash("Row deleted.", "success")
    elif action == "add":
        if db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] >= MAX_ROWS:
            flash(f"You can have at most {MAX_ROWS} rows.", "error")
        else:
            position = db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM clients").fetchone()[0]
            new_id = db.execute("INSERT INTO clients (position) VALUES (?)", (position,)).lastrowid
            anchor = f"row-{new_id}"
    elif action == "generate":
        if _generate(db):
            anchor = "invoices"
    else:
        flash("Saved.", "success")
    db.commit()
    return redirect(url_for("views.generator", _anchor=anchor))


@bp.post("/clear")
def clear():
    """Clear Invoices: delete generated invoices and restart numbering at 001."""
    db = get_db()
    db.execute("DELETE FROM invoices")
    db.execute("UPDATE clients SET count = NULL")
    set_setting(db, "next_number", 1)
    db.commit()
    flash("Invoices cleared. Numbering restarts at 001.", "success")
    return redirect(url_for("views.generator"))


@bp.get("/invoices/<int:invoice_pk>.pdf")
def invoice_pdf(invoice_pk):
    inv = _invoice(get_db(), invoice_pk)
    if inv is None:
        return redirect(url_for("views.generator"))
    pdf = render_invoice(dict(inv), current_app.config["COMPANY"])
    return send_file(BytesIO(pdf), mimetype="application/pdf", download_name=f"{inv['sheet_name']}.pdf",
                     as_attachment=request.args.get("download") == "1")


@bp.get("/export.zip")
def export():
    """Export: all generated invoices as PDFs in one zip."""
    rows = get_db().execute("SELECT * FROM invoices ORDER BY id").fetchall()
    if not rows:
        flash("There are no invoices to export yet.", "error")
        return redirect(url_for("views.generator"))
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in rows:
            zf.writestr(f"{inv['sheet_name']}.pdf", render_invoice(dict(inv), current_app.config["COMPANY"]))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"invoices-{rows[0]['invoice_date']}.zip")
