document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-contact-details-form]");

  if (!form) {
    return;
  }

  event.preventDefault();

  const targetSelector = form.dataset.target;
  const target = document.querySelector(targetSelector);

  if (!target) {
    return;
  }

  const submitButton = form.querySelector('button[type="submit"]');
  const originalButtonText = submitButton ? submitButton.textContent : null;
  const loadingButtonText = submitButton?.dataset.loadingText || "Saving...";

  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = loadingButtonText;
  }

  try {
    const response = await fetch(form.action, {
      method: form.method,
      body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    const html = await response.text();
    target.outerHTML = html;

    initContactDetailsPhoneInput();
  } catch (error) {
    console.error("Contact details form submit failed:", error);

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  }
});

function formatCanadianPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 10);

  if (digits.length <= 3) {
    return digits ? `(${digits}` : "";
  }

  if (digits.length <= 6) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  }

  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

function initContactDetailsPhoneInput() {
  const phoneInput = document.getElementById("id_phone");

  if (!phoneInput) {
    return;
  }

  phoneInput.value = formatCanadianPhone(phoneInput.value);

  phoneInput.addEventListener("input", () => {
    phoneInput.value = formatCanadianPhone(phoneInput.value);
  });
}

initContactDetailsPhoneInput();