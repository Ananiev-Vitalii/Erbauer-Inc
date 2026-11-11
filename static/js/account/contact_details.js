(() => {
  function parseResponse(html, currentForm, target) {
    if (/<\s*(?:!doctype\b|\/?(?:html|head|body)\b)/i.test(html)) {
      throw new Error("Unexpected response document");
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
      !partial.matches('div[data-profile-form-response="contact"]') ||
      partial.id !== target.id ||
      partial.children.length !== 1 ||
      Array.from(partial.childNodes).some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
      ) ||
      partial.querySelectorAll("form").length !== 1 ||
      partial.querySelector(
        "[data-profile-form-response], script, style, link, meta, base, iframe, object, embed"
      )
    ) {
      throw new Error("Unexpected response partial");
    }
    const form = partial.firstElementChild;
    const csrfFields = form.querySelectorAll('input[name="csrfmiddlewaretoken"]');
    const action = new URL(form.getAttribute("action") || "", document.baseURI);
    if (
      !form.matches("form[data-contact-details-form]") ||
      form.getAttribute("method")?.toLowerCase() !== "post" ||
      action.href !== currentForm.action ||
      action.origin !== window.location.origin ||
      form.dataset.target !== currentForm.dataset.target ||
      csrfFields.length !== 1 ||
      csrfFields[0].type !== "hidden" ||
      !csrfFields[0].value ||
      !["phone","email","street_address","city","province","postal_code"].every((name) => form.elements.namedItem(name)) ||
      !form.querySelector('button[type="submit"]')
    ) {
      throw new Error("Unexpected response form");
    }
    return partial;
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-contact-details-form]");
    if (!form) return;
    event.preventDefault();
    if (form.dataset.submitting === "true") return;
    const target = document.querySelector(form.dataset.target);
    if (!target || !target.contains(form)) return;

    form.dataset.submitting = "true";
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton?.textContent;
    let errorMessage = form.dataset.submitError;
    form.querySelector("[data-profile-submit-error]")?.remove();
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = submitButton.dataset.loadingText || originalButtonText;
    }
    try {
      const response = await fetch(form.action, {
        method: "POST",
        redirect: "manual",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "text/html",
        },
      });
      if (
        response.type === "opaqueredirect" || response.redirected ||
        [301, 302, 303, 307, 308, 401, 403].includes(response.status)
      ) {
        errorMessage = form.dataset.sessionError;
        throw new Error("Session or redirect response");
      }
      const contentType = (response.headers.get("Content-Type") || "")
        .split(";", 1)[0].trim().toLowerCase();
      if (![200, 400, 422].includes(response.status) || contentType !== "text/html") {
        throw new Error("Unexpected response status or content type");
      }
      const partial = parseResponse(await response.text(), form, target);
      initContactDetailsInputs(partial);
      target.replaceWith(partial);
    } catch (error) {
      console.error("Profile form request failed:", error);
      const message = document.createElement("div");
      message.className = "profile-form-error";
      message.dataset.profileSubmitError = "";
      message.setAttribute("role", "alert");
      message.textContent = errorMessage;
      form.prepend(message);
    } finally {
      form.dataset.submitting = "false";
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
      }
    }
  });

  const completePhonePattern = /^(?:\+?1 ?)?([0-9]{10}|[0-9]{3}([ .-])[0-9]{3}\2[0-9]{4}|\([0-9]{3}\) [0-9]{3}-[0-9]{4})$/;

  function formatNationalPhone(digits) {
    if (!digits) return "";
    if (digits.length < 4) return "(" + digits;
    if (digits.length < 7) return "(" + digits.slice(0, 3) + ") " + digits.slice(3);
    return "(" + digits.slice(0, 3) + ") " + digits.slice(3, 6) + "-" + digits.slice(6);
  }

  function formatPhoneInput(value, allowPartial) {
    const match = completePhonePattern.exec(value.trim());
    if (match) return formatNationalPhone(match[1].replace(/[ ().-]/g, ""));
    if (!allowPartial) return value;
    const isPartial = /^[0-9]{0,10}$/.test(value) ||
      /^\([0-9]{0,3}$/.test(value) ||
      /^\([0-9]{3}\) [0-9]{0,3}$/.test(value) ||
      /^\([0-9]{3}\) [0-9]{3}-[0-9]{0,4}$/.test(value);
    return isPartial ? formatNationalPhone(value.replace(/[ ()-]/g, "")) : value;
  }

  function initContactDetailsInputs(root = document) {
    const phone = root.querySelector("#id_phone");
    if (phone && phone.dataset.maskInitialized !== "true") {
      phone.dataset.maskInitialized = "true";
      phone.removeAttribute("maxlength");
      phone.value = formatPhoneInput(phone.value, false);
      phone.addEventListener("input", (event) => {
        const allowPartial = (event.inputType === "insertText" && event.data?.length === 1) ||
          event.inputType?.startsWith("delete");
        phone.value = formatPhoneInput(phone.value, allowPartial);
      });
      phone.addEventListener("paste", (event) => {
        if (!event.clipboardData) return;
        event.preventDefault();
        phone.setRangeText(
          event.clipboardData.getData("text"), phone.selectionStart, phone.selectionEnd, "end"
        );
        phone.value = formatPhoneInput(phone.value, false);
      });
    }
    const postalCode = root.querySelector("#id_postal_code");
    if (postalCode && postalCode.dataset.maskInitialized !== "true") {
      postalCode.dataset.maskInitialized = "true";
      postalCode.removeAttribute("maxlength");
      const formatPostalCode = (value) => {
        if (/[^\x00-\x7F]/.test(value)) return value;
        const normalized = value.trim().toUpperCase();
        const complete = /^[ABCEGHJ-NPRSTVXY][0-9][ABCEGHJ-NPRSTV-Z] ?[0-9][ABCEGHJ-NPRSTV-Z][0-9]$/;
        if (complete.test(normalized)) {
          return normalized.slice(0, 3) + " " + normalized.slice(-3);
        }
        if (/^[A-Z0-9]{4,6}$/.test(normalized)) {
          return normalized.slice(0, 3) + " " + normalized.slice(3);
        }
        return normalized;
      };
      postalCode.value = formatPostalCode(postalCode.value);
      postalCode.addEventListener("input", () => {
        postalCode.value = formatPostalCode(postalCode.value);
      });
    }
  }

  initContactDetailsInputs();
})();
