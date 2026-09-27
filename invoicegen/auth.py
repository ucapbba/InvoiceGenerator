"""Director logins, CSRF protection and user-management commands.

There is no sign-up page: users are created on the server with
    flask --app invoicegen add-user NAME
"""

import secrets
import time

import click
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

MAX_FAILED_LOGINS = 5
LOCK_SECONDS = 15 * 60
MIN_PASSWORD_LENGTH = 12
# Checked against when the username doesn't exist, so both cases take the same time.
_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe())

bp = Blueprint("auth", __name__)


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _check_csrf():
    if request.method != "POST":
        return
    expected = session.get("csrf")
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400, "Form expired - go back, refresh the page and try again.")


def _load_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        now = time.time()
        locked = user is not None and user["locked_until"] is not None and user["locked_until"] > now
        password_ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)

        if user and password_ok and not locked:
            db.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
            db.commit()
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            return redirect(url_for("views.generator"))

        if user and not locked:
            failed = user["failed_logins"] + 1
            if failed >= MAX_FAILED_LOGINS:
                db.execute("UPDATE users SET failed_logins = 0, locked_until = ? WHERE id = ?", (now + LOCK_SECONDS, user["id"]))
            else:
                db.execute("UPDATE users SET failed_logins = ? WHERE id = ?", (failed, user["id"]))
            db.commit()
        flash(f"Incorrect username or password. After {MAX_FAILED_LOGINS} failed attempts the account "
              f"is locked for {LOCK_SECONDS // 60} minutes.", "error")
    return render_template("login.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


def _prompt_password() -> str:
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise click.ClickException(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


@click.command("add-user")
@click.argument("username")
def add_user_command(username):
    """Create a director login."""
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise click.ClickException(f"User '{username}' already exists - use set-password.")
    db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, generate_password_hash(_prompt_password())))
    db.commit()
    click.echo(f"Created user '{username}'.")


@click.command("set-password")
@click.argument("username")
def set_password_command(username):
    """Change a user's password (also unlocks the account)."""
    db = get_db()
    cur = db.execute("UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL WHERE username = ?",
                     (generate_password_hash(_prompt_password()), username))
    if cur.rowcount == 0:
        raise click.ClickException(f"No user '{username}'.")
    db.commit()
    click.echo(f"Password updated for '{username}'.")


@click.command("delete-user")
@click.argument("username")
def delete_user_command(username):
    """Remove a login. Anyone logged in as that user is signed out on their next click."""
    db = get_db()
    if db.execute("DELETE FROM users WHERE username = ?", (username,)).rowcount == 0:
        raise click.ClickException(f"No user '{username}'.")
    db.commit()
    click.echo(f"Deleted user '{username}'.")


@click.command("list-users")
def list_users_command():
    """Show all logins."""
    for row in get_db().execute("SELECT username, locked_until FROM users ORDER BY username"):
        locked = " (locked)" if row["locked_until"] and row["locked_until"] > time.time() else ""
        click.echo(row["username"] + locked)


def init_app(app):
    app.register_blueprint(bp)
    app.before_request(_load_user)
    app.before_request(_check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
    for command in (add_user_command, set_password_command, delete_user_command, list_users_command):
        app.cli.add_command(command)
