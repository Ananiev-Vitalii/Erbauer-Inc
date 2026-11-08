document.addEventListener("DOMContentLoaded", () => {
  const filtersWrap = document.getElementById("projectFilters");
  const projectCards = Array.from(document.querySelectorAll(".projects__card"));

  if (filtersWrap) {
    const filterButtons = Array.from(
      filtersWrap.querySelectorAll(".projects__filter")
    );

    filtersWrap.addEventListener("click", (event) => {
      const button = event.target.closest(".projects__filter");
      if (!button) return;

      const selectedFilter = button.dataset.filter;

      filterButtons.forEach((btn) => {
        btn.classList.toggle("is-active", btn === button);
      });

      projectCards.forEach((card) => {
        const cardCategory = card.dataset.category;
        const shouldShow =
          selectedFilter === "all" || cardCategory === selectedFilter;

        card.classList.toggle("hide-project", !shouldShow);
      });
    });
  }

  const lightbox = document.getElementById("projectsLightbox");
  const lightboxImage = document.getElementById("projectsLightboxImage");
  const lightboxClose = document.getElementById("projectsLightboxClose");
  const imageButtons = Array.from(
    document.querySelectorAll(".projects__image-icon")
  );

  if (!lightbox || !lightboxImage || !lightboxClose) return;

  let openingTrigger = null;
  let cleanupTimer = null;
  lightboxClose.tabIndex = -1;

  const canFocus = (element) => element?.isConnected &&
    !element.matches(":disabled") &&
    !element.closest('[inert], [hidden], [aria-hidden="true"]') &&
    element.getClientRects().length > 0 &&
    getComputedStyle(element).visibility === "visible";

  const openLightbox = (imageSrc, imageAlt, trigger) => {
    if (!imageSrc) return;

    clearTimeout(cleanupTimer);
    cleanupTimer = null;
    openingTrigger = trigger;

    lightboxImage.src = imageSrc;
    lightboxImage.alt = imageAlt;
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("lightbox-open");
    lightboxClose.tabIndex = 0;
    if (canFocus(lightboxClose)) lightboxClose.focus({ preventScroll: true });
  };

  const closeLightbox = () => {
    if (!lightbox.classList.contains("is-open")) return;

    lightbox.classList.remove("is-open");
    lightboxClose.tabIndex = -1;
    if (canFocus(openingTrigger)) openingTrigger.focus({ preventScroll: true });
    openingTrigger = null;
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("lightbox-open");

    clearTimeout(cleanupTimer);
    cleanupTimer = setTimeout(() => {
      cleanupTimer = null;
      if (!lightbox.classList.contains("is-open")) {
        lightboxImage.removeAttribute("src");
        lightboxImage.alt = "";
      }
    }, 280);
  };

  imageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      openLightbox(button.dataset.image, button.dataset.alt || "", button);
    });
  });

  if (lightbox) {
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox || event.target.matches(
        "[data-lightbox-close], .projects-lightbox__dialog"
      )) {
        closeLightbox();
      }
    });
  }

  if (lightboxClose) {
    lightboxClose.addEventListener("click", closeLightbox);
  }

  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("is-open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeLightbox();
    } else if (event.key === "Tab") {
      // The close button is the only interactive control inside this dialog.
      event.preventDefault();
      if (canFocus(lightboxClose)) lightboxClose.focus({ preventScroll: true });
    }
  });

  document.addEventListener("focusin", (event) => {
    if (lightbox.classList.contains("is-open") &&
        !lightbox.contains(event.target) && canFocus(lightboxClose)) {
      lightboxClose.focus({ preventScroll: true });
    }
  });
});
