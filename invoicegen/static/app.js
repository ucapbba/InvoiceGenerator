// Page behaviour. Kept in this file because the Content-Security-Policy blocks inline scripts.

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 4000);
}

// Ask before destructive buttons (Delete row, Clear invoices).
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-confirm]");
  if (button && !confirm(button.dataset.confirm)) event.preventDefault();
});

// Email buttons: hand the invoice PDF to the phone's mail app (e.g. Outlook) via the share menu.
// The PDFs are fetched when the page loads, because phones only allow sharing straight after a tap.
const readyFiles = new Map();

function prepare(button) {
  fetch(button.dataset.pdf, { credentials: "same-origin" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.blob();
    })
    .then((blob) => {
      readyFiles.set(button, new File([blob], button.dataset.filename, { type: "application/pdf" }));
    })
    .catch(() => { button.dataset.failed = "1"; });
}

function emailInvoice(button) {
  const { to, subject, body, filename } = button.dataset;
  const file = readyFiles.get(button);

  if (navigator.canShare && !file && !button.dataset.failed) {
    toast("Still preparing the PDF - tap again in a moment.");
    return;
  }

  if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
    // Mail apps don't take a recipient from the share menu, so put it on the clipboard to paste.
    navigator.clipboard?.writeText(to).catch(() => {});
    navigator.share({ files: [file], title: subject, text: body }).catch((err) => {
      if (err.name !== "AbortError") toast(`Couldn't share: ${err.message}`);
    });
    toast(`Choose Outlook. ${to} is copied - paste it into To.`);
    return;
  }

  // No share menu (most desktop browsers): download the PDF and open a pre-filled email to attach it to.
  const link = document.createElement("a");
  link.href = `${button.dataset.pdf}?download=1`;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => {
    window.location.href = `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }, 500);
  toast("PDF downloaded - attach it to the email.");
}

document.querySelectorAll(".js-email").forEach((button) => {
  prepare(button);
  button.addEventListener("click", () => emailInvoice(button));
});
