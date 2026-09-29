# Invoice Generator server

How the live site at **https://invoices.beaaugstein.co.uk** is hosted, how to connect
to the server, how to update and restart the app, and what was set up to get here.

Nothing secret is in this file: no passwords, private keys or tunnel credentials.

## How it fits together

```
Director's browser
      │  https://invoices.beaaugstein.co.uk
      ▼
Cloudflare ── Always Use HTTPS
      │      ── Access: email one-time code, "Directors" policy
      │  (outgoing tunnel, started by the server; no router ports open)
      ▼
Ubuntu PC (192.168.1.105)
  ├─ invoices-tunnel service   cloudflared → http://127.0.0.1:8100
  └─ invoicegen service        the app (Waitress), app login, SQLite database
```

A visitor has to pass **two locks**: Cloudflare's email code (only addresses listed
in the Access policy get one), then the app's own username and password.

## What's where

| | |
|---|---|
| **Server** | Lenovo IdeaCentre G5, Ubuntu 22.04, hostname `bradley-IdeaCentre-G5-14IMB05` |
| **Address** | `192.168.1.105` on the home network, user `bradley`, SSH port 22 |
| **Host key fingerprint** | `SHA256:BWjGdy57JKqKSTHKoHhZ842lB2YCCt3dglO6Q55KsWQ` (ED25519) |
| **App code** | `~/InvoiceGenerator` (copied from this repo; it's not a git checkout) |
| **App's Python** | `~/InvoiceGenerator/.venv`, built from Ubuntu's Python 3.10 |
| **Data** | `~/InvoiceGenerator/instance/`: `invoices.db` (clients, invoices, logins), `secret_key`, optional `company.json` |
| **Tunnel** | `~/.local/bin/cloudflared`, config `~/.cloudflared/config.yml`, credentials `~/.cloudflared/5509d4fa-….json` |
| **Services** | `~/.config/systemd/user/invoicegen.service` and `invoices-tunnel.service` |
| **Development copy** | This repo, in the VS Code dev container (on its own Docker volume, not visible from the Mac Terminal). Its `instance/` data is **out of date**; don't run `./run.sh` here to use the app. |

> **Python on the server:** plain `python3` there is a hand-built 3.12 in `/usr/local`
> **without SQLite**, so it can't open the database. Always use the app's
> `.venv/bin/python` (or `/usr/bin/python3.10`).

## Connecting with SSH

The server only accepts **SSH keys** (no passwords), only for user `bradley`, and
the firewall only lets **the Mac (192.168.1.63)** reach SSH. So you need to be
on the home network, on the Mac.

Two places can connect, both using **your Mac key** (`~/.ssh/id_ed25519`). It's the
only key the server accepts, and it only works from the Mac's address.

### From the Mac's own Terminal

```bash
ssh bradley@192.168.1.105
```

### From the VS Code terminal (dev container)

The container stores no key. VS Code forwards the Mac's SSH agent into it, so once the key
is loaded on the Mac (**Mac Terminal:** `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`),
this works in the VS Code terminal:

```bash
ssh bradley@192.168.1.105
```

`ssh-add -l` shows whether the key is loaded; `ssh-add -D` (Mac Terminal) unloads it.

### Adding another key

For example a new laptop, or a temporary key for a Claude session. From a machine that can
already log in, add the new **public** key (one line starting `ssh-ed25519`, safe to share),
keeping the "only from the Mac" restriction:

```bash
echo 'from="192.168.1.63",no-agent-forwarding,no-X11-forwarding PASTE-THE-PUBLIC-KEY-LINE' \
  | ssh bradley@192.168.1.105 'cat >> ~/.ssh/authorized_keys'
```

To remove a key, delete its line from `~/.ssh/authorized_keys` on the server.
A key used from a different address also needs a new firewall rule (`sudo ufw allow from IP to any port 22 proto tcp`).

### VS Code on the server

Install the **Remote - SSH** extension, run **Remote-SSH: Connect to Host…** and use
`bradley@192.168.1.105`. You get the server's files and a terminal inside VS Code.

## Updating the app after a code change

Use the deploy script. In the VS Code terminal, in this folder:

```bash
./deploy.sh --dry-run   # optional: see which files would change
./deploy.sh
```

It tests, copies, updates libraries if needed, tests again on the server, then restarts
the app. See [DEPLOY.md](DEPLOY.md) for details and troubleshooting.

## Running the services

Run these **on the server** (after `ssh`-ing in). No `sudo` needed: both are
"user" services belonging to `bradley`.

| Task | Command |
|---|---|
| Status of both | `systemctl --user status invoicegen invoices-tunnel` |
| Restart the app | `systemctl --user restart invoicegen` |
| Restart the tunnel | `systemctl --user restart invoices-tunnel` |
| Stop / start | `systemctl --user stop invoicegen` / `systemctl --user start invoicegen` |
| App log (live) | `journalctl --user -u invoicegen -f` |
| Tunnel log (last 50 lines) | `journalctl --user -u invoices-tunnel -n 50` |

Both services start at boot **without anyone logging in** (lingering is on for
`bradley`) and restart themselves 5 seconds after a crash.

## Managing director logins

On the server:

```bash
cd ~/InvoiceGenerator
.venv/bin/flask --app invoicegen add-user NAME       # asks for a password, 12+ characters
.venv/bin/flask --app invoicegen set-password NAME   # change it, also unlocks a locked account
.venv/bin/flask --app invoicegen delete-user NAME
.venv/bin/flask --app invoicegen list-users
```

A new director also needs their email address added to Cloudflare Access:
**Zero Trust → Access → Applications → Invoice Generator → Policies → Directors → Include → Emails**.

## Data and backups

Everything that matters is in `~/InvoiceGenerator/instance/` on the server.

**Backups are not set up yet.** The `Data` partition (`/media/bradley/Data`) is on
the **same physical disk** as Ubuntu, so it doesn't protect against that disk
failing. Use a USB drive or cloud storage instead.

To take a safe copy of the database while the app is running (on the server):

```bash
/usr/bin/python3.10 -c "import sqlite3; s=sqlite3.connect('/home/bradley/InvoiceGenerator/instance/invoices.db'); d=sqlite3.connect('/home/bradley/invoices-backup.db'); s.backup(d)"
```

Also keep a copy of `instance/secret_key` and `instance/company.json`. Store backups
somewhere private, since they contain client data and login details.

## Cloudflare settings (dashboard)

| Setting | Where | Value |
|---|---|---|
| Domain | Websites | `beaaugstein.co.uk` (Free plan) |
| DNS | DNS → Records | `invoices` CNAME to the tunnel, created by `cloudflared tunnel route dns` |
| HTTPS certificate | SSL/TLS → Edge Certificates | Universal (free, auto-renews) |
| Always Use HTTPS | SSL/TLS → Edge Certificates | On |
| Tunnel | Zero Trust → Networks → Tunnels | `invoices` (ID `5509d4fa-47fb-4e14-8215-709f9b949f5a`) |
| Login method | Zero Trust → Settings → Authentication | One-time PIN |
| Access application | Zero Trust → Access → Applications | Invoice Generator, `invoices.beaaugstein.co.uk`, policy **Directors** (Allow, Include → Emails) |

The Cloudflare **account certificate** (`~/.cloudflared/cert.pem`, needed only to
create, delete or re-route tunnels) is kept in the dev container, **not** on the server.

## What was done to set this up

**On the Mac / dev container**
1. Built the app (Flask + Waitress + ReportLab, SQLite) and tested it locally on port 8100.
2. Installed `cloudflared`, authorised it for `beaaugstein.co.uk` (`cloudflared tunnel login`),
   created the tunnel `invoices` and pointed `invoices.beaaugstein.co.uk` at it.
3. Turned on Always Use HTTPS, then set up Cloudflare Access with One-time PIN and the Directors policy.
4. Created a temporary SSH key (`agent_key`) in the container for Claude to do the setup, and
   checked the server's host key against the fingerprint above before trusting it. That key was
   removed from the server once setup was finished; only the Mac key remains.

**On the server (security, done with the Claude session running there)**
1. Firewall (`ufw`): deny all incoming, allow outgoing, allow SSH only from `192.168.1.63`.
   Check with `sudo ufw status verbose`.
2. SSH hardening in `/etc/ssh/sshd_config.d/10-hardening.conf`: no passwords, no
   root login, keys only, only user `bradley`, 3 attempts max, no X11. Written before
   the SSH server was installed, so it never ran with passwords allowed.
3. Installed `openssh-server` and `fail2ban` (blocks addresses that keep failing to log in).
4. Added keys to `~/.ssh/authorized_keys`, each restricted to connections from
   `192.168.1.63` with agent and X11 forwarding off: first Claude's temporary key (since
   removed), then the Mac key (`ucapbba@Bradleys-MBP.lan`).
5. **No passwordless `sudo`**: anything logged in over SSH can use `bradley`'s files but
   can't become root without the password.

**On the server (app)**
1. Copied the code with `rsync` (no git history, dev environment or spreadsheet).
2. Installed `python3.10-venv` (sudo) and built `.venv` from Ubuntu's Python 3.10,
   since the `/usr/local` Python 3.12 lacks SQLite. All tests passed.
3. Copied `instance/` (database snapshot and secret key) with owner-only permissions.
4. Copied the `cloudflared` program and the tunnel config and credentials (paths changed
   to `/home/bradley`). The account certificate was deliberately left behind.
5. Created the two user services and turned on lingering (`sudo loginctl enable-linger bradley`).
6. Switchover: stopped the app on the Mac, copied the final database, started both
   services on the server, then stopped the Mac's tunnel. Cloudflare now shows a single
   `linux_amd64` connector.

## Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| Cloudflare **502 Bad Gateway** | Tunnel is up but the app isn't answering. On the server: `systemctl --user status invoicegen`, then `journalctl --user -u invoicegen -n 50`; `systemctl --user restart invoicegen`. |
| Cloudflare **1033** or the site doesn't load | Tunnel is down, or the server is off or asleep. Check `systemctl --user status invoices-tunnel` and the tunnel log. |
| **SSH times out** | You're not on the home network, the Mac's address has changed from 192.168.1.63 (the firewall blocks it), or the server is off or booted into Windows. |
| **SSH "Permission denied (publickey)"** | The Mac key isn't loaded (`ssh-add -l`; load it with `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` in the Mac Terminal), or you're not connecting from 192.168.1.63. |
| **Mac's address changed** | At the server's own keyboard: `sudo ufw allow from NEW_IP to any port 22 proto tcp`, then update the `from="…"` in `~/.ssh/authorized_keys`. Better: set a DHCP reservation for the Mac in the router. |
| **Dev container rebuilt** | The container's `~/.ssh/known_hosts` and `~/.cloudflared/cert.pem` are gone. SSH asks to confirm the server: only accept fingerprint `SHA256:BWjGdy57JKqKSTHKoHhZ842lB2YCCt3dglO6Q55KsWQ`. Run `cloudflared tunnel login` again only if you need to manage tunnels. The live site is unaffected. |
| **Login keeps returning to the login page** | Logins only work over HTTPS. Use the `https://` address. |
| **"Too many failed attempts"** | Wait 15 minutes, or on the server: `.venv/bin/flask --app invoicegen set-password NAME`. |

### Still to check or do
- **Sleep:** make sure the server never sleeps or suspends (Settings → Power, or ask about masking the sleep targets).
- **Boot default:** GRUB is set to the first menu entry with a 10-second timeout. Confirm that entry is Ubuntu, so the server comes back in Ubuntu after a restart or power cut.
- **Reboot test:** restart the server without logging in, and check the site comes back by itself.
- **Backups:** choose a USB drive or cloud target and set up a daily copy.
- **Updates:** `sudo apt update && sudo apt upgrade` now and then. For `cloudflared`, copy in a newer binary and restart `invoices-tunnel` (it runs with `--no-autoupdate`).
