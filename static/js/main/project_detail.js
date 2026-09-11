document.addEventListener("DOMContentLoaded", () => {
  const lightbox = document.getElementById("projectLightbox");
  const lightboxImage = document.getElementById("projectLightboxImage");
  const closeButton = document.getElementById("projectLightboxClose");
  const triggers = document.querySelectorAll(".project-lightbox-trigger");
  const closeTargets = document.querySelectorAll("[data-lightbox-close]");

  if (!lightbox || !lightboxImage || !closeButton || !triggers.length) {
    return;
  }

  const openLightbox = (src, alt = "") => {
    lightboxImage.src = src;
    lightboxImage.alt = alt;
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("project-lightbox-open");
  };

  const closeLightbox = () => {
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("project-lightbox-open");

    setTimeout(() => {
      lightboxImage.src = "";
      lightboxImage.alt = "";
    }, 200);
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const src = trigger.dataset.image;
      const alt = trigger.dataset.alt || "";

      if (!src) {
        return;
      }

      openLightbox(src, alt);
    });
  });

  closeButton.addEventListener("click", closeLightbox);

  closeTargets.forEach((target) => {
    target.addEventListener("click", closeLightbox);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox.classList.contains("is-open")) {
      closeLightbox();
    }
  });
});