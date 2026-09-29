#!/usr/bin/env bash
# Deploy this folder's code to the invoice server and restart the app.
#
#   ./deploy.sh             test locally, copy, test on the server, restart
#   ./deploy.sh --dry-run   only show which files would change
#
# Run it from the VS Code terminal. It logs in with your Mac's SSH key, which VS Code
# forwards into the dev container (load it on the Mac first: ssh-add --apple-use-keychain).
# See DEPLOY.md.
set -euo pipefail
cd "$(dirname "$0")"

SERVER="${INVOICEGEN_SERVER:-bradley@192.168.1.105}"
REMOTE_DIR="InvoiceGenerator"
# Extra ssh options, e.g. INVOICEGEN_SSH_OPTS="-i ~/.ssh/other_key -o IdentitiesOnly=yes"
SSH_OPTS="${INVOICEGEN_SSH_OPTS:-}"

DRY_RUN=0
case "${1:-}" in
  "") ;;
  --dry-run) DRY_RUN=1 ;;
  *) echo "Usage: ./deploy.sh [--dry-run]" >&2; exit 2 ;;
esac

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31mDeploy stopped: %s\033[0m\n' "$1" >&2; exit 1; }
remote() { ssh $SSH_OPTS "$SERVER" "$@"; }

[ -f invoicegen/__init__.py ] || fail "run this from the InvoiceGenerator folder"

step "Checking the connection to $SERVER"
if [ -z "$SSH_OPTS" ] && ! ssh-add -l >/dev/null 2>&1; then
  fail "no SSH key available. On the Mac Terminal run:  ssh-add --apple-use-keychain ~/.ssh/id_ed25519
  then try again."
fi
remote true || fail "can't log in to $SERVER (on the home network? Mac key loaded?)"
echo "OK"

FILTERS=(
  --exclude '.git/' --exclude '.venv/' --exclude 'instance/' --exclude '*.xlsm'
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude 'DEPLOYED.txt'
)
RSYNC=(rsync -az --delete --itemize-changes -e "ssh $SSH_OPTS" "${FILTERS[@]}" ./ "$SERVER:$REMOTE_DIR/")

if [ "$DRY_RUN" = 1 ]; then
  step "Files that would change (dry run, nothing copied)"
  "${RSYNC[@]}" --dry-run | grep -v '/$' || echo "(no changes)"
  exit 0
fi

step "Running the tests here"
[ -x .venv/bin/python ] || fail "no local .venv - run ./run.sh once to create it"
.venv/bin/python -m pytest -q || fail "tests failed here, nothing was deployed"

step "Copying code"
old_requirements=$(remote "sha256sum $REMOTE_DIR/requirements.txt 2>/dev/null | cut -d' ' -f1" || true)
"${RSYNC[@]}" | grep -v '/$' || echo "(no file changes)"

if [ "$old_requirements" != "$(sha256sum requirements.txt | cut -d' ' -f1)" ]; then
  step "requirements.txt changed - updating the server's libraries"
  remote "cd $REMOTE_DIR && .venv/bin/pip install -q -r requirements.txt"
fi

step "Running the tests on the server"
remote "cd $REMOTE_DIR && .venv/bin/python -m pytest -q" \
  || fail "tests failed on the server. The new code is copied but the app was NOT restarted, so the old version is still running."

step "Restarting the app"
version="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
git diff --quiet HEAD 2>/dev/null || version="$version plus uncommitted changes"
printf 'Deployed %s from %s\nVersion: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$(hostname)" "$version" \
  | remote "cat > $REMOTE_DIR/DEPLOYED.txt"
remote "systemctl --user restart invoicegen && sleep 2 && systemctl --user is-active --quiet invoicegen" \
  || fail "the app didn't start. Check the log on the server: journalctl --user -u invoicegen -n 50"
remote "$REMOTE_DIR/.venv/bin/python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/login', timeout=10)\"" \
  || fail "the app is running but not answering. Check: journalctl --user -u invoicegen -n 50"

step "Done"
echo "Deployed version: $version"
echo "Live at https://invoices.beaaugstein.co.uk"
