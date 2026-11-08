document.addEventListener("DOMContentLoaded", () => {
  const lightbox = document.getElementById("projectLightbox");
  const lightboxImage = document.getElementById("projectLightboxImage");
  const closeButton = document.getElementById("projectLightboxClose");
  const triggers = document.querySelectorAll(".project-lightbox-trigger");

  if (!lightbox || !lightboxImage || !closeButton || !triggers.length) {
    return;
  }

  let openingTrigger = null;
  let cleanupTimer = null;
  closeButton.tabIndex = -1;

  const canFocus = (element) => element?.isConnected &&
    !element.matches(":disabled") &&
    !element.closest('[inert], [hidden], [aria-hidden="true"]') &&
    element.getClientRects().length > 0 &&
    getComputedStyle(element).visibility === "visible";

  const openLightbox = (src, alt, trigger) => {
    clearTimeout(cleanupTimer);
    cleanupTimer = null;
    openingTrigger = trigger;
    lightboxImage.src = src;
    lightboxImage.alt = alt;
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("project-lightbox-open");
    closeButton.tabIndex = 0;
    if (canFocus(closeButton)) closeButton.focus({ preventScroll: true });
  };

  const closeLightbox = () => {
    if (!lightbox.classList.contains("is-open")) return;

    lightbox.classList.remove("is-open");
    closeButton.tabIndex = -1;
    if (canFocus(openingTrigger)) openingTrigger.focus({ preventScroll: true });
    openingTrigger = null;
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("project-lightbox-open");

    clearTimeout(cleanupTimer);
    cleanupTimer = setTimeout(() => {
      cleanupTimer = null;
      if (!lightbox.classList.contains("is-open")) {
        lightboxImage.removeAttribute("src");
        lightboxImage.alt = "";
      }
    }, 280);
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const src = trigger.dataset.image;
      const alt = trigger.dataset.alt || "";

      if (!src) {
        return;
      }

      openLightbox(src, alt, trigger);
    });
  });

  closeButton.addEventListener("click", closeLightbox);

  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox || event.target.matches(
      "[data-lightbox-close], .project-lightbox__dialog, .project-lightbox__stage"
    )) {
      closeLightbox();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("is-open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeLightbox();
    } else if (event.key === "Tab") {
      // The close button is the only interactive control inside this dialog.
      event.preventDefault();
      if (canFocus(closeButton)) closeButton.focus({ preventScroll: true });
    }
  });

  document.addEventListener("focusin", (event) => {
    if (lightbox.classList.contains("is-open") &&
        !lightbox.contains(event.target) && canFocus(closeButton)) {
      closeButton.focus({ preventScroll: true });
    }
  });
});
