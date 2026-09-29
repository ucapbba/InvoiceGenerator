# Deploying code changes

`./deploy.sh` copies the code in this folder to the invoice server and restarts the
app. For how the server itself is set up, see [SERVER.md](SERVER.md).

## Quick version

1. **Mac Terminal** (once per Mac restart; the Keychain remembers the passphrase):
   ```bash
   ssh-add --apple-use-keychain ~/.ssh/id_ed25519
   ```
2. **VS Code terminal**, in this folder:
   ```bash
   ./deploy.sh --dry-run   # optional: see which files would change
   ./deploy.sh
   ```

You need to be on the home network, on the Mac.

## What the script does

1. **Checks it can log in** to `bradley@192.168.1.105`.
2. **Runs the tests here.** If any fail, it stops and nothing is copied.
3. **Copies the code** with `rsync` and lists every changed file. It never copies or
   deletes the server's data (`instance/`), its Python environment (`.venv/`), the git
   history or the spreadsheet. Files you've deleted here are deleted on the server too.
4. **Updates the server's libraries**, only if `requirements.txt` changed.
5. **Runs the tests on the server.** If they fail, it stops *without restarting*,
   so the previous version keeps running.
6. **Restarts the app** and checks it's answering.
7. **Records the deployed version** in `~/InvoiceGenerator/DEPLOYED.txt` on the server:
   the date, and the git commit (noting "plus uncommitted changes" if there were any).

Deploying takes about 30 seconds. The site is only down for the couple of seconds of the restart.

## Why the key lives on the Mac

This project folder lives on the dev container's own disk (a Docker volume), so the
Mac Terminal can't see it and the script has to run in the VS Code terminal. The
container doesn't store any key: VS Code **forwards your Mac's SSH agent** into it. So:

- The script uses your Mac key (`~/.ssh/id_ed25519`) while it's loaded with `ssh-add`.
- The connection still comes from the Mac's address (192.168.1.63), which is the only
  address the server's firewall and `authorized_keys` accept.
- To unload the key (so nothing in the container can use it): `ssh-add -D` in the Mac Terminal.
- Check what's loaded: `ssh-add -l` (works in either terminal).

If your key has no passphrase yet, add one: `ssh-keygen -p -f ~/.ssh/id_ed25519`.

## If something goes wrong

| Message | What to do |
|---|---|
| `no SSH key available` | Run `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` in the Mac Terminal. |
| `can't log in` | Are you on the home network? Is the server on and in Ubuntu? Has the Mac's IP changed from 192.168.1.63? |
| `tests failed here` | Fix the code. Nothing was deployed. |
| `tests failed on the server` | Usually a library difference. The old version is still running; see the test output. |
| `the app didn't start` / `not answering` | On the server: `journalctl --user -u invoicegen -n 50`. |
| Asked `Are you sure you want to continue connecting?` | Normal after the dev container is rebuilt. Only type `yes` if the fingerprint shown is `SHA256:BWjGdy57JKqKSTHKoHhZ842lB2YCCt3dglO6Q55KsWQ`. |

**Rolling back:** check out the previous version in git (e.g. `git stash`, or
`git checkout <commit> -- .`), run `./deploy.sh`, then return to your latest code.

## Settings

The defaults suit this setup. To override for one run:

| Variable | Default | Use |
|---|---|---|
| `INVOICEGEN_SERVER` | `bradley@192.168.1.105` | a different server or user |
| `INVOICEGEN_SSH_OPTS` | none | extra `ssh` options, e.g. `-i ~/.ssh/other_key -o IdentitiesOnly=yes` |
