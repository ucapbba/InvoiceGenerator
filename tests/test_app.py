import io
import zipfile

from conftest import csrf_from, log_in, sheet_form
from invoicegen.auth import MAX_FAILED_LOGINS
from invoicegen.db import get_db


def test_pages_need_login(client):
    for url in ("/", "/export.zip", "/invoices/1.pdf"):
        response = client.get(url)
        assert response.status_code == 302 and response.location.endswith("/login")
    assert client.post("/sheet").status_code == 400  # no CSRF token without a session


def test_login_and_logout(client):
    assert log_in(client).location.endswith("/")
    assert "Ms A Sample" in client.get("/").get_data(as_text=True)
    client.post("/logout", data={"csrf_token": csrf_from(client.get("/"))})
    assert client.get("/").status_code == 302


def test_wrong_password_is_rejected(client):
    response = log_in(client, password="wrong")
    assert response.status_code == 200
    assert "Incorrect username or password" in response.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_account_locks_after_repeated_failures(client):
    for _ in range(MAX_FAILED_LOGINS):
        log_in(client, password="wrong")
    log_in(client)  # right password, but locked
    assert client.get("/").status_code == 302


def test_post_without_csrf_token_is_rejected(logged_in):
    assert logged_in.post("/sheet", data={"action": "clear"}).status_code == 400
    assert logged_in.post("/sheet", data={"action": "clear", "csrf_token": "forged"}).status_code == 400


def test_deleted_user_is_signed_out(app, logged_in):
    with app.app_context():
        get_db().execute("DELETE FROM users")
        get_db().commit()
    assert logged_in.get("/").status_code == 302


def test_security_headers(logged_in):
    response = logged_in.get("/")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_save_edits_a_row(logged_in):
    form = sheet_form(logged_in)
    form["name"][0] = "Mx Z Edited"
    form["action"] = "save"
    logged_in.post("/sheet", data=form)
    assert "Mx Z Edited" in logged_in.get("/").get_data(as_text=True)


def test_add_and_delete_rows(logged_in):
    form = sheet_form(logged_in)
    count = len(form["id"])
    logged_in.post("/sheet", data={**form, "action": "add"})
    form = sheet_form(logged_in)
    assert len(form["id"]) == count + 1
    logged_in.post("/sheet", data={**form, "delete": form["id"][0]})
    assert len(sheet_form(logged_in)["id"]) == count


def test_generate_export_and_clear(logged_in):
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    page = logged_in.get("/").get_data(as_text=True)
    assert "Generated 6 invoices" in page
    assert "10-2026-001" in page and "10-2026-006" in page
    assert "Smith1" in page
    # Unit with email gets an Email link that opens the email app with address and subject.
    assert 'href="mailto:a.sample@example.com?subject=Invoice%2010-2026-001&amp;body=Dear%20Ms%20A%20Sample' in page
    assert "Houses aren't emailed" in page

    # Generating again without clearing is refused, as in the spreadsheet.
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    assert "Please clear existing invoices" in logged_in.get("/").get_data(as_text=True)

    pdf = logged_in.get("/invoices/1.pdf")
    assert pdf.mimetype == "application/pdf" and pdf.data.startswith(b"%PDF")

    archive = zipfile.ZipFile(io.BytesIO(logged_in.get("/export.zip").data))
    assert sorted(archive.namelist()) == sorted(
        ["Sample.pdf", "Example.pdf", "Smith.pdf", "Smith1.pdf", "Placeholder.pdf", "Tenant.pdf"])

    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "clear"})
    page = logged_in.get("/").get_data(as_text=True)
    assert "No invoices generated yet" in page
    assert 'Next invoice ID: <strong id="next-id">10-2026-007</strong>' in page  # numbering carries on


def test_generate_reports_bad_rows_and_creates_nothing(logged_in):
    form = sheet_form(logged_in)
    form["amount"][1] = "lots"
    logged_in.post("/sheet", data={**form, "action": "generate"})
    page = logged_in.get("/").get_data(as_text=True)
    assert "Row 2 (Mr B Example): amount &#39;lots&#39; is not a number" in page
    assert "No invoices generated yet" in page


def test_invoice_number_is_remembered_and_increments(logged_in):
    form = sheet_form(logged_in)
    logged_in.post("/sheet", data={**form, "next_number": "42", "action": "save"})
    assert sheet_form(logged_in)["next_number"] == "42"

    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    page = logged_in.get("/").get_data(as_text=True)
    assert "10-2026-042" in page and "10-2026-047" in page
    assert sheet_form(logged_in)["next_number"] == "48"


def test_clear_saves_a_typed_number(logged_in):
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    logged_in.post("/sheet", data={**sheet_form(logged_in), "next_number": "100", "action": "clear"})
    assert sheet_form(logged_in)["next_number"] == "100"
