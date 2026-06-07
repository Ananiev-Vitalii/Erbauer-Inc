function initSimpleInvoicePostalCodeInput(root = document) {
  const postalCodeInput = root.querySelector("#id_postal_code");

  if (!postalCodeInput) {
    return;
  }

  const formatPostalCode = (value) => {
    let formattedValue = value
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "")
      .slice(0, 6);

    if (formattedValue.length > 3) {
      formattedValue = `${formattedValue.slice(0, 3)} ${formattedValue.slice(3)}`;
    }

    return formattedValue;
  };

  postalCodeInput.value = formatPostalCode(postalCodeInput.value);

  postalCodeInput.addEventListener("input", () => {
    postalCodeInput.value = formatPostalCode(postalCodeInput.value);
  });
}

function initSimpleInvoiceForm(root = document) {
  const form = root.querySelector("[data-simple-invoice-form]");

  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const targetSelector = form.dataset.target;
    const target = document.querySelector(targetSelector);

    if (!target) {
      return;
    }

    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton ? submitButton.textContent : null;
    const loadingButtonText = submitButton?.dataset.loadingText || "Sending invoice...";

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

      const updatedTarget = document.querySelector(targetSelector);

      if (updatedTarget) {
        initSimpleInvoicePostalCodeInput(updatedTarget);
        initSimpleInvoiceForm(updatedTarget);
      }
    } catch (error) {
      console.error("Simple invoice form submit failed:", error);

      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
      }
    }
  });
}

initSimpleInvoicePostalCodeInput();
initSimpleInvoiceForm();