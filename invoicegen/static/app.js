// Page behaviour. Kept in this file because the Content-Security-Policy blocks inline scripts.

// Ask before destructive buttons (Delete row, Clear invoices).
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-confirm]");
  if (button && !confirm(button.dataset.confirm)) event.preventDefault();
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
