document.addEventListener("DOMContentLoaded", function () {
  const wrapper = document.getElementById("contactFormWrapper");
  if (!wrapper) {
    console.warn("contactFormWrapper not found");
    return;
  }

  function formatCanadianPhone(value) {
    const digits = value.replace(/\D/g, "").slice(0, 10);

    if (digits.length === 0) return "";
    if (digits.length < 4) return `(${digits}`;
    if (digits.length < 7) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
  }

  function setSubmitLoading(form, isLoading) {
    const submitButton = form.querySelector(".contacts__submit");

    if (!submitButton) return;

    submitButton.disabled = isLoading;
    submitButton.classList.toggle("is-loading", isLoading);
  }

  function bindContactForm() {
    const form = wrapper.querySelector("#contactForm");

    if (!form) {
      console.warn("contactForm not found inside wrapper");
      return;
    }

    const phoneInput = form.querySelector(".contacts__input--phone");

    if (phoneInput) {
      phoneInput.addEventListener("input", function (event) {
        event.target.value = formatCanadianPhone(event.target.value);
      });

      phoneInput.addEventListener("paste", function (event) {
        event.preventDefault();
        const pasted = (event.clipboardData || window.clipboardData).getData("text");
        phoneInput.value = formatCanadianPhone(pasted);
      });
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();

      setSubmitLoading(form, true);

      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
          },
        });

        const html = await response.text();
        wrapper.innerHTML = html;
        bindContactForm();
      } catch (error) {
        console.error("Contact form AJAX error:", error);
        setSubmitLoading(form, false);
      }
    });
  }

  bindContactForm();
});