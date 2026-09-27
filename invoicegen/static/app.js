// Page behaviour. Kept in this file because the Content-Security-Policy blocks inline scripts.

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 5000);
}

// Ask before destructive buttons (Delete row, Clear invoices).
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-confirm]");
  if (button && !confirm(button.dataset.confirm)) event.preventDefault();
});

// Email links open the email app with the address, subject and message filled in.
// Email links can't carry attachments, so download the PDF at the same time to attach.
document.querySelectorAll(".js-email").forEach((link) => {
  link.addEventListener("click", () => {
    const download = document.createElement("a");
    download.href = link.dataset.pdf;
    download.download = link.dataset.filename;
    document.body.append(download);
    download.click();
    download.remove();
    toast(`${link.dataset.filename} downloaded - attach it to the email.`);
  });
});

// Show the next invoice ID as the date or number is typed (same format as the server: 10-2026-001).
const dateInput = document.querySelector("input[name=invoice_date]");
const numberInput = document.querySelector("input[name=next_number]");
const nextId = document.getElementById("next-id");

function updateNextId() {
  const [year, month] = dateInput.value.split("-").map(Number);
  const number = parseInt(numberInput.value, 10);
  if (year && month && number >= 1) {
    nextId.textContent = `${month}-${year}-${String(number).padStart(3, "0")}`;
  }
}

if (dateInput && numberInput && nextId) {
  dateInput.addEventListener("input", updateNextId);
  numberInput.addEventListener("input", updateNextId);
}
