import email
import io
import zipfile
from email import policy

import pytest

from conftest import PASSWORD, csrf_from, log_in, sheet_form
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
    assert "<strong>Smith1</strong>" in page
    assert page.count(">Email</a>") == 5  # everyone with an email address, Houses included

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


def test_email_is_an_outlook_draft_with_the_pdf_attached(logged_in):
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    response = logged_in.get("/invoices/1.eml")
    assert response.mimetype == "message/rfc822"
    assert "Sample_10-2026-001.eml" in response.headers["Content-Disposition"]

    msg = email.message_from_bytes(response.data, policy=policy.default)
    assert msg["To"] == "a.sample@example.com"
    assert msg["Subject"] == "Invoice 10-2026-001"
    assert msg["X-Unsent"] == "1"  # Outlook opens it as a draft
    assert "Attached is your invoice 10-2026-001 for Example Farm Unit 1." in msg.get_body(("plain",)).get_content()
    [attachment] = list(msg.iter_attachments())
    assert attachment.get_filename() == "Sample.pdf"
    assert attachment.get_content().startswith(b"%PDF")


def test_rows_without_email_get_no_draft_but_houses_do(logged_in):
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    assert logged_in.get("/invoices/4.eml").status_code == 302  # Mr D Smith, no email address
    assert logged_in.get("/invoices/6.eml").status_code == 200  # House with an email address


def test_all_drafts_zip(logged_in):
    logged_in.post("/sheet", data={**sheet_form(logged_in), "action": "generate"})
    archive = zipfile.ZipFile(io.BytesIO(logged_in.get("/drafts.zip").data))
    assert sorted(archive.namelist()) == sorted(
        ["Sample_10-2026-001.eml", "Example_10-2026-002.eml", "Smith_10-2026-003.eml", "Placeholder_10-2026-005.eml",
         "Tenant_10-2026-006.eml"])


def test_auth_check_reports_whether_logged_in(client):
    assert client.get("/auth/check").status_code == 401
    log_in(client)
    assert client.get("/auth/check").status_code == 204


def _log_in_with_next(client, next_url):
    token = csrf_from(client.get("/login"))
    return client.post("/login", data={"csrf_token": token, "username": "director", "password": PASSWORD,
                                       "next": next_url})


@pytest.mark.parametrize("next_url", ["https://beaaugstein.co.uk/docs", "https://fund.beaaugstein.co.uk/", "/export.zip"])
def test_login_returns_to_pages_on_the_site(app, client, next_url):
    app.config["SITE_DOMAIN"] = "beaaugstein.co.uk"
    assert _log_in_with_next(client, next_url).location == next_url


@pytest.mark.parametrize("next_url", ["https://evil.example/", "//evil.example/", "https://beaaugstein.co.uk.evil.example/",
                                      "http://beaaugstein.co.uk/", "/\\evil.example", "javascript:alert(1)"])
def test_login_never_redirects_off_the_site(app, client, next_url):
    app.config["SITE_DOMAIN"] = "beaaugstein.co.uk"
    assert _log_in_with_next(client, next_url).location == "/"


def test_without_site_domain_only_local_pages_are_allowed(client):
    assert _log_in_with_next(client, "https://beaaugstein.co.uk/").location == "/"


def test_site_domain_makes_the_login_cover_the_whole_site(monkeypatch, tmp_path):
    monkeypatch.setenv("INVOICEGEN_SITE_DOMAIN", "beaaugstein.co.uk")
    from invoicegen import create_app
    app = create_app({"TESTING": True}, instance_path=str(tmp_path))
    response = app.test_client().get("/login")
    assert response.headers["Set-Cookie"].startswith("bea_session=")
    assert "Domain=beaaugstein.co.uk" in response.headers["Set-Cookie"]
    assert "form-action 'self' https://beaaugstein.co.uk https://*.beaaugstein.co.uk" in response.headers["Content-Security-Policy"]
