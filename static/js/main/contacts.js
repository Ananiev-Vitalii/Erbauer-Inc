document.addEventListener("DOMContentLoaded", function () {
  const wrapper = document.getElementById("contactFormWrapper");
  if (!wrapper) {
    console.warn("contactFormWrapper not found");
    return;
  }

  let requestInProgress = false;

  const completePhonePattern = new RegExp(
    "^(?:\\+?1 ?)?(" +
    "[0-9]{10}|[0-9]{3}([ .-])[0-9]{3}\\2[0-9]{4}|" +
    "\\([0-9]{3}\\) [0-9]{3}-[0-9]{4})$"
  );

  function formatNationalPhone(digits) {

    if (digits.length === 0) return "";
    if (digits.length < 4) return `(${digits}`;
    if (digits.length < 7) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
  }

  function formatCompletePhone(value) {
    const match = completePhonePattern.exec(value.trim());
    if (!match) return null;
    // Strip only validated national-number separators, never arbitrary input.
    return formatNationalPhone(match[1].replace(/[ ().-]/g, ""));
  }

  function formatPhoneInput(value, allowPartial) {
    const complete = formatCompletePhone(value);
    if (complete !== null) return complete;
    if (!allowPartial) return value;

    // Only raw digits or intermediate states produced by our own mask qualify.
    const isPartial = /^[0-9]{0,10}$/.test(value) ||
      /^\([0-9]{0,3}$/.test(value) ||
      /^\([0-9]{3}\) [0-9]{0,3}$/.test(value) ||
      /^\([0-9]{3}\) [0-9]{3}-[0-9]{0,4}$/.test(value);
    return isPartial
      ? formatNationalPhone(value.replace(/[ ()-]/g, ""))
      : value;
  }

  function setSubmitLoading(form, isLoading) {
    const submitButton = form.querySelector(".contacts__submit");

    if (!submitButton) return;

    submitButton.disabled = isLoading;
    submitButton.classList.toggle("is-loading", isLoading);
  }

  function showSubmitError(form) {
    let message = form.querySelector("[data-contact-submit-error]");
    if (!message) {
      message = document.createElement("p");
      message.className = "error-message";
      message.setAttribute("data-contact-submit-error", "");
      message.setAttribute("role", "alert");
      form.prepend(message);
    }
    message.textContent = wrapper.dataset.submitError;
  }

  function parseContactPartial(html, currentForm) {
    // Fragment parsing may discard document tags, so reject documents first.
    if (/<\s*(?:!doctype\b|\/?(?:html|head|body)\b)/i.test(html)) {
      throw new Error("Unexpected contact response document");
    }

    const template = document.createElement("template");
    template.innerHTML = html;
    const nodes = Array.from(template.content.childNodes).filter(
      (node) => node.nodeType !== Node.COMMENT_NODE &&
        !(node.nodeType === Node.TEXT_NODE && !node.textContent.trim())
    );
    const partial = nodes[0];
    if (
      nodes.length !== 1 ||
      partial.nodeType !== Node.ELEMENT_NODE ||
      !partial.matches("div[data-contact-form-response]") ||
      partial.children.length !== 1 ||
      Array.from(partial.childNodes).some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
      ) ||
      partial.querySelectorAll("form").length !== 1 ||
      partial.querySelector(
        "[data-contact-form-response], #contactFormWrapper, " +
        "script, style, link, meta, base, iframe, object, embed"
      )
    ) {
      throw new Error("Unexpected contact response structure");
    }

    const form = partial.firstElementChild;
    const csrfFields = form.querySelectorAll('input[name="csrfmiddlewaretoken"]');
    const expectedFields = ["name", "phone", "message", "privacy_policy"];
    const action = new URL(form.getAttribute("action") || "", document.baseURI);
    if (
      !form.matches("form#contactForm") ||
      form.getAttribute("method")?.toLowerCase() !== "post" ||
      action.href !== currentForm.action ||
      action.origin !== window.location.origin ||
      csrfFields.length !== 1 ||
      csrfFields[0].type !== "hidden" ||
      !csrfFields[0].value ||
      !expectedFields.every((name) => form.elements.namedItem(name)) ||
      !form.querySelector('button.contacts__submit[type="submit"]')
    ) {
      throw new Error("Unexpected contact response form");
    }

    return partial;
  }

  function bindContactForm(form = wrapper.querySelector("#contactForm")) {
    if (!form) {
      console.warn("contactForm not found inside wrapper");
      return;
    }

    const phoneInput = form.querySelector(".contacts__input--phone");

    if (phoneInput) {
      phoneInput.addEventListener("input", function (event) {
        const allowPartial =
          (event.inputType === "insertText" && event.data?.length === 1) ||
          event.inputType?.startsWith("delete");
        phoneInput.value = formatPhoneInput(phoneInput.value, allowPartial);
      });

      phoneInput.addEventListener("paste", function (event) {
        const clipboard = event.clipboardData || window.clipboardData;
        if (!clipboard) return;
        event.preventDefault();
        const pasted = clipboard.getData("text");
        phoneInput.setRangeText(
          pasted, phoneInput.selectionStart, phoneInput.selectionEnd, "end"
        );
        // Invalid pasted content stays visible and reaches server validation.
        phoneInput.value = formatPhoneInput(phoneInput.value, false);
      });
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (requestInProgress) return;
      requestInProgress = true;

      try {
        setSubmitLoading(form, true);
        form.querySelector("[data-contact-submit-error]")?.remove();
        const response = await fetch(form.action, {
          method: "POST",
          redirect: "error",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/html",
          },
        });

        const contentType = (response.headers.get("Content-Type") || "")
          .split(";", 1)[0].trim().toLowerCase();
        if (
          ![200, 503].includes(response.status) ||
          response.redirected ||
          contentType !== "text/html"
        ) {
          throw new Error("Unexpected contact response");
        }

        const html = await response.text();
        const partial = parseContactPartial(html, form);
        bindContactForm(partial.firstElementChild);
        wrapper.replaceChildren(partial);
      } catch (error) {
        console.error("Contact form AJAX error:", error);
        showSubmitError(form);
      } finally {
        requestInProgress = false;
        setSubmitLoading(form, false);
        const currentForm = wrapper.querySelector("#contactForm");
        if (currentForm && currentForm !== form) {
          setSubmitLoading(currentForm, false);
        }
      }
    });
  }

  bindContactForm();
});
