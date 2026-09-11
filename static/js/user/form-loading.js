document.addEventListener("DOMContentLoaded", () => {
  const forms = document.querySelectorAll(".base-form");

  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      const submitButton = form.querySelector('button[type="submit"]');

      if (!submitButton) return;

      submitButton.disabled = true;
      submitButton.classList.add("is-loading");
    });
  });
});