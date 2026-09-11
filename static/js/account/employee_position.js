document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-employee-position-form]");

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
  } catch (error) {
    console.error("Employee position form submit failed:", error);

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  }
});