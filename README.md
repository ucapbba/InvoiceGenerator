# InvoiceGenerator

A phone-friendly web version of the Excel VBA invoice generator (`InvoiceGenerator3.1.xlsm`).

It works like the spreadsheet:

| Spreadsheet | Web app |
|---|---|
| Generator sheet (Name, Amount, Property Name, Address, Type, Email, Count) | **Clients** table |
| B2 Invoice ID, B3 Date | **Next invoice no.** and **Invoice date** |
| Generate button | **Generate invoices**: one invoice per row (Smith, Smith1... for repeated surnames) |
| Invoice Template Units / Houses | PDF with the same layout; Units add 20% VAT, Houses don't |
| Export button | **PDF** on each invoice, or **Export all PDFs (zip)** |
| Send Email button | **Email** on each Unit invoice with an email address: opens the phone's share menu, where you pick Outlook |
| Clear Invoices button | **Clear invoices**: removes generated invoices, numbering restarts at 001 |

The app starts with made-up sample clients. Company details on the invoice are placeholders
too; see [Company details](#company-details).

## Running it

```bash
./run.sh
```

It listens on `http://127.0.0.1:8100` only, so it can't be reached from the network directly.
Put it on the internet through a Cloudflare Tunnel (below), which also provides HTTPS.

### Director logins

There's no sign-up page. Create logins on the machine running the app:

```bash
.venv/bin/flask --app invoicegen add-user alice      # prompts for a password (12+ characters)
.venv/bin/flask --app invoicegen set-password alice  # change it, also unlocks a locked account
.venv/bin/flask --app invoicegen delete-user alice
.venv/bin/flask --app invoicegen list-users
```

After 5 wrong passwords an account is locked for 15 minutes. Logins expire after 8 hours of inactivity.

### Testing over plain http

Login cookies are only sent over HTTPS. `http://localhost` works in Chrome, Edge and Firefox.
For anything else over plain http (only on a network you trust), start it with:

```bash
INVOICEGEN_INSECURE_COOKIES=1 ./run.sh
```

## Company details

Invoices use the placeholder details in `invoicegen/company.py`. To use real ones, create
`instance/company.json` with the same keys (it's excluded from git):

```json
{
  "name": "Company Name",
  "address": ["Line 1", "Line 2", "Town", "County POSTCODE"],
  "tel": "01234 567890",
  "vat_reg": "123 4567 89",
  "bank": ["Bank details for direct debit payment: Bank plc,", "Sort code: ... Account Number: ...", "Account name: ..."],
  "correspondence_heading": "Please send any written correspondence including cheques to:",
  "correspondence": "Address for correspondence"
}
```

## Cloudflare Tunnel

With `cloudflared` installed on the machine running the app:

```bash
cloudflared tunnel login
cloudflared tunnel create invoices
cloudflared tunnel route dns invoices invoices.your-domain.co.uk
cloudflared tunnel run --url http://127.0.0.1:8100 invoices
```

For an extra layer, add a Cloudflare Access policy for that hostname that only lets the
directors' email addresses through.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Data

Everything is stored in `instance/invoices.db` (SQLite) with the session key in
`instance/secret_key`. Back up the `instance/` folder. To keep it somewhere else (e.g. on a
server), set `INVOICEGEN_INSTANCE=/path/to/folder` for both `run.sh` and the `flask` commands.
