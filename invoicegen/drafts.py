"""Email drafts as .eml files: the web version of the VBA's CreateEmails, which saved .msg files.

The X-Unsent header makes Outlook for Windows open the file as a new draft, with the
recipient, subject, message and PDF attachment filled in, ready to send.
"""

from email import policy
from email.message import EmailMessage
from html import escape

from .generator import email_body, email_subject


def draft_filename(invoice) -> str:
    """Same naming as the VBA's .msg files: Surname_InvoiceID."""
    return f"{invoice['sheet_name']}_{invoice['invoice_id']}.eml"


def build_draft(invoice, company, pdf: bytes) -> bytes:
    msg = EmailMessage()
    msg["To"] = invoice["email"]
    if company.get("email_cc"):
        msg["Cc"] = company["email_cc"]
    msg["Subject"] = email_subject(invoice)
    msg["X-Unsent"] = "1"

    body = email_body(invoice, company)
    msg.set_content(body)
    paragraphs = "".join(f"<p>{escape(p).replace(chr(10), '<br>')}</p>" for p in body.split("\n\n"))
    msg.add_alternative(f"<html><body>{paragraphs}</body></html>", subtype="html")
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"{invoice['sheet_name']}.pdf")
    return msg.as_bytes(policy=policy.SMTP)
