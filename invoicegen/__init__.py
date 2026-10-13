"""Invoice Generator: a web version of the Excel VBA invoice generator."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask

from .company import load_company


def _secret_key(path: Path) -> str:
    """Session signing key, created once and kept in the instance folder."""
    if not path.exists():
        path.touch(mode=0o600)
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def create_app(test_config=None, instance_path=None):
    # Data folder (database, secret key, company.json). Defaults to ./instance next to the code.
    instance_path = instance_path or os.environ.get("INVOICEGEN_INSTANCE")
    if instance_path:
        instance_path = os.path.abspath(instance_path)
    app = Flask(__name__, instance_path=instance_path, instance_relative_config=True)
    # e.g. beaaugstein.co.uk: the login then covers that domain and all its subdomains (the home
    # and fund apps ask /auth/check). Unset locally, so the cookie stays on this host only.
    site_domain = os.environ.get("INVOICEGEN_SITE_DOMAIN") or None
    instance = Path(app.instance_path)
    instance.mkdir(mode=0o700, parents=True, exist_ok=True)
    app.config.update(
        DATABASE=str(instance / "invoices.db"),
        SECRET_KEY=_secret_key(instance / "secret_key"),
        COMPANY=load_company(app.instance_path),
        SITE_DOMAIN=site_domain,
        SESSION_COOKIE_DOMAIN=site_domain,
        # Its own name, so an old invoices-only "session" cookie in the browser can't shadow it.
        SESSION_COOKIE_NAME="bea_session" if site_domain else "session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Cookies only travel over HTTPS. Set INVOICEGEN_INSECURE_COOKIES=1 to test over plain http.
        SESSION_COOKIE_SECURE=os.environ.get("INVOICEGEN_INSECURE_COOKIES") != "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    from . import auth, db, views
    db.init_app(app)
    auth.init_app(app)
    app.register_blueprint(views.bp)

    # Browsers apply form-action to the redirect after logging in, so allow the rest of the site.
    form_action = "'self'" + (f" https://{site_domain} https://*.{site_domain}" if site_domain else "")

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; object-src 'none'; "
            f"base-uri 'none'; form-action {form_action}; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if response.mimetype == "text/html" or response.mimetype == "application/pdf":
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
