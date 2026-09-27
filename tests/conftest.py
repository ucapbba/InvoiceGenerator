import re

import pytest
from werkzeug.security import generate_password_hash

from invoicegen import create_app
from invoicegen.db import get_db

PASSWORD = "correct horse battery"


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False, "DATABASE": str(tmp_path / "test.db")},
                     instance_path=str(tmp_path))
    from invoicegen.db import init_db
    init_db(app.config["DATABASE"])
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("director", generate_password_hash(PASSWORD)))
        db.execute("UPDATE settings SET value = '2026-10-01' WHERE key = 'invoice_date'")
        db.commit()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_from(response) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)


def log_in(client, username="director", password=PASSWORD):
    token = csrf_from(client.get("/login"))
    return client.post("/login", data={"csrf_token": token, "username": username, "password": password})


@pytest.fixture
def logged_in(client):
    log_in(client)
    return client


def sheet_form(client) -> dict:
    """The Generator form as the browser would submit it, from the current page."""
    page = client.get("/").get_data(as_text=True)
    form = {"csrf_token": csrf_from(client.get("/")),
            "invoice_date": re.search(r'name="invoice_date" value="([^"]*)"', page).group(1),
            "next_number": re.search(r'name="next_number"[^>]*value="([^"]*)"', page).group(1)}
    for field in ("id", "name", "amount", "property", "address", "email"):
        form[field] = re.findall(rf'name="{field}" value="([^"]*)"', page)
    form["type"] = re.findall(r"<option selected>(\w+)</option>", page)
    return form
